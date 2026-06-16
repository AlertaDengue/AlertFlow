# flake8: noqa: E501

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.sdk import Variable, task

PYTHON_ENV_PATH = "/opt/airflow/envs/geospatial_env/bin/python"

BRAZIL_STATES = [
    "AC",
    "AL",
    "AM",
    "AP",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MG",
    "MS",
    "MT",
    "PA",
    "PB",
    "PE",
    "PI",
    "PR",
    "RJ",
    "RN",
    "RO",
    "RR",
    "RS",
    "SC",
    "SE",
    "SP",
    "TO",
]

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
}

uri = Variable.get("psql_main_uri", deserialize_json=True)

with DAG(
    dag_id="VEGETATION_INDEX_METRICS",
    default_args=default_args,
    start_date=datetime(2020, 1, 1),
    schedule=timedelta(days=16),
    catchup=True,
    tags=["geospatial", "vegetation"],
    max_active_runs=2,
) as vegetation_dag:

    @task.external_python(python=PYTHON_ENV_PATH)
    def run_state_pipeline(
        target_uf: str,
        base_date: str,
        database_uri: str,
        grid_cache: str,
    ) -> None:
        import gc
        import logging
        import sys
        import time
        import warnings
        from collections import defaultdict
        from datetime import date as dt_date
        from datetime import datetime as dt_class
        from datetime import timedelta as dt_timedelta
        from pathlib import Path
        from typing import Any, Callable, Dict, List, Tuple, TypeVar, cast

        import geobr
        import geopandas as gpd
        import numpy as np
        import pandas as pd
        import pystac_client
        import rasterio
        from affine import Affine
        from pydantic import BaseModel, BeforeValidator, ConfigDict, Field
        from rasterio.errors import NotGeoreferencedWarning
        from rasterio.io import MemoryFile
        from rasterio.mask import mask
        from rasterio.merge import merge
        from rasterio.warp import transform_bounds
        from rasterstats import zonal_stats
        from shapely.geometry import mapping
        from shapely.geometry.base import BaseGeometry
        from sqlalchemy import create_engine, text
        from sqlalchemy.engine import Engine
        from typing_extensions import Annotated

        logger = logging.getLogger()
        handler = logging.StreamHandler(sys.stdout)
        logger.addHandler(handler)
        logging.basicConfig(
            level=logging.INFO,
            format="[%(levelname)s] %(message)s",
        )
        print("stdout")
        print("stderr", file=sys.stderr)

        start_dt = dt_class.strptime(base_date, "%Y-%m-%d")
        end_dt = start_dt + dt_timedelta(days=16)

        start_ds = base_date
        end_ds = end_dt.strftime("%Y-%m-%d")

        logger.info(f"{start_ds} - {end_ds}")

        BAND_SPECS_RAW: Dict[str, Dict[str, Any]] = {
            "red_reflectance": {
                "aliases": ["red_reflectance", "250m_16_days_red_reflectance"],
                "scale": 0.0001,
                "nodata": -1000,
            },
            "NIR_reflectance": {
                "aliases": ["NIR_reflectance", "250m_16_days_NIR_reflectance"],
                "scale": 0.0001,
                "nodata": -1000,
            },
            "MIR_reflectance": {
                "aliases": ["MIR_reflectance", "250m_16_days_MIR_reflectance"],
                "scale": 0.0001,
                "nodata": -1000,
            },
            "NDVI": {
                "aliases": ["NDVI", "250m_16_days_NDVI"],
                "scale": 0.0001,
                "nodata": -3000,
            },
            "EVI": {
                "aliases": ["EVI", "250m_16_days_EVI"],
                "scale": 0.0001,
                "nodata": -3000,
            },
        }

        T = TypeVar("T")

        def num_to_none(v: Any) -> Any:
            if v is None:
                return None
            try:
                if np.isnan(v):
                    return None
            except TypeError:
                pass
            return v

        CleanFloat: Annotated = Annotated[float | None, BeforeValidator(num_to_none)]

        class MetricRecord(BaseModel):
            model_config = ConfigDict(arbitrary_types_allowed=True)
            date: dt_date
            geocode: int
            collection: str
            attribute: str
            mean: CleanFloat = Field(default=None)
            std: CleanFloat = Field(default=None)
            median: CleanFloat = Field(default=None)
            q25: CleanFloat = Field(default=None)
            q75: CleanFloat = Field(default=None)
            min: CleanFloat = Field(default=None)
            max: CleanFloat = Field(default=None)

        class CollectionMetrics(BaseModel):
            records: list[MetricRecord] = Field(default_factory=list)

            @property
            def is_empty(self) -> bool:
                return len(self.records) == 0

        class MunicipalityGeoRecord(BaseModel):
            model_config = ConfigDict(arbitrary_types_allowed=True)
            geocode: int
            uf: str
            geometry: BaseGeometry

        class MunicipalityCollection(BaseModel):
            model_config = ConfigDict(arbitrary_types_allowed=True)
            municipalities: list[MunicipalityGeoRecord] = Field(default_factory=list)
            crs: Any = Field(default="EPSG:4674")

            def to_gdf(self) -> gpd.GeoDataFrame:
                if not self.municipalities:
                    return gpd.GeoDataFrame(
                        columns=["geocode", "uf", "geometry"], crs=self.crs
                    )
                data = [
                    {"geocode": m.geocode, "uf": m.uf, "geometry": m.geometry}
                    for m in self.municipalities
                ]
                return gpd.GeoDataFrame(data, crs=self.crs)

        class StacAssetRecord(BaseModel):
            href: str

        class StacItemRecord(BaseModel):
            datetime: dt_class
            assets: Dict[str, StacAssetRecord]

        class BandSpec(BaseModel):
            aliases: List[str]
            scale: float
            nodata: int

        class RasterStackOutput(BaseModel):
            model_config = ConfigDict(arbitrary_types_allowed=True)
            band_arrays: Dict[str, np.ndarray]
            profile: Dict[str, Any]

        BAND_SPECS = {name: BandSpec(**spec) for name, spec in BAND_SPECS_RAW.items()}
        BASE_BANDS = list(BAND_SPECS)

        def execute_with_retry(operation: Callable[[], T]) -> T:
            for attempt in range(1, 4):
                try:
                    return operation()
                except Exception as exc:
                    logger.warning(f"Operation failed on attempt {attempt}/3: {exc}")
                    if attempt >= 3:
                        raise
                    time.sleep(2.0 * (2 ** (attempt - 1)))
            raise RuntimeError("Max attempts exceeded")

        def load_municipalities_optimized(
            grid_cache: str, target_uf: str | None = None
        ) -> MunicipalityCollection:
            path = Path(grid_cache)
            if not path.exists():
                logger.info("Initializing municipality cache via geobr.")
                path.parent.mkdir(parents=True, exist_ok=True)
                munis_download: Any = geobr.read_municipality(year=2020)
                assert isinstance(munis_download, gpd.GeoDataFrame)
                munis_download.to_file(path, driver="GPKG")
            if target_uf:
                sql = f"SELECT * FROM municipios_br_2020 WHERE abbrev_state = '{target_uf.upper()}'"
                munis_raw: Any = gpd.read_file(path, sql=sql)
            else:
                munis_raw = gpd.read_file(path)
            assert isinstance(munis_raw, gpd.GeoDataFrame)
            munis = munis_raw.copy()
            munis["geocode"] = munis["code_muni"].astype(int)
            munis["uf"] = munis["abbrev_state"].str.upper()
            records = []
            for _, row in munis.iterrows():
                row_any: Any = row
                records.append(
                    MunicipalityGeoRecord(
                        geocode=int(row_any["geocode"]),
                        uf=str(row_any["uf"]),
                        geometry=cast(BaseGeometry, row_any["geometry"]),
                    )
                )
            logger.info(f"Loaded {len(records)} municipalities for target {target_uf}")
            return MunicipalityCollection(municipalities=records, crs=munis.crs)

        def fetch_stac_range(
            collection: str,
            state_munis: gpd.GeoDataFrame,
            start_date: str,
            end_date: str,
        ) -> List[StacItemRecord]:
            stac_period = f"{start_date}T00:00:00Z/{end_date}T23:59:59Z"
            kwargs = {
                "collections": [collection],
                "bbox": tuple(state_munis.to_crs(4326).total_bounds),
                "datetime": stac_period,
            }

            def fetch() -> List[StacItemRecord]:
                client = pystac_client.Client.open("https://data.inpe.br/bdc/stac/v1/")
                search = client.search(**kwargs)
                records = []
                for item in search.items():
                    if item.datetime is None:
                        continue
                    asset_dict = {}
                    for key, asset in item.assets.items():
                        asset_dict[key] = StacAssetRecord(href=asset.href)
                    records.append(
                        StacItemRecord(datetime=item.datetime, assets=asset_dict)
                    )
                return sorted(records, key=lambda x: x.datetime)

            return execute_with_retry(fetch)

        def open_raster_stack_in_memory(
            urls_by_band: Dict[str, List[str]],
            state_bounds: Tuple[float, ...],
            state_geom: BaseGeometry,
            bands: List[str],
        ) -> RasterStackOutput | None:
            def _task() -> RasterStackOutput | None:
                first_band = next(
                    (band for band in bands if urls_by_band.get(band)), None
                )
                if not first_band:
                    return None
                urls_for_band = urls_by_band[first_band]
                if not urls_for_band:
                    return None
                with rasterio.open(urls_for_band[0]) as first_src:
                    first_transform: Any = first_src.transform
                    first_affine = (
                        first_transform
                        if isinstance(first_transform, Affine)
                        else Affine(*first_transform)
                    )
                    crs_val: Any = first_src.crs
                    if crs_val is None or first_affine.almost_equals(
                        Affine.identity(),
                    ):
                        return None
                    raster_crs = crs_val
                    reproj_bounds = transform_bounds(
                        "EPSG:4326",
                        raster_crs,
                        *state_bounds,
                        densify_pts=21,
                    )
                    geom_proj = (
                        gpd.GeoSeries(
                            [state_geom],
                            crs=4326,
                        )
                        .to_crs(raster_crs)
                        .iloc[0]
                    )
                band_arrays = {}
                profile_ref = None
                for band in bands:
                    urls = urls_by_band.get(band, [])
                    if not urls:
                        continue
                    opened_srcs = [rasterio.open(url) for url in urls]
                    try:
                        srcs = []
                        for src in opened_srcs:
                            src_transform: Any = src.transform
                            src_affine = (
                                src_transform
                                if isinstance(src_transform, Affine)
                                else Affine(*src_transform)
                            )
                            if src.crs is None or src_affine.almost_equals(
                                Affine.identity()
                            ):
                                continue
                            src_bounds: Any = src.bounds
                            if not (
                                src_bounds.right <= reproj_bounds[0]
                                or src_bounds.left >= reproj_bounds[2]
                                or src_bounds.top <= reproj_bounds[1]
                                or src_bounds.bottom >= reproj_bounds[3]
                            ):
                                srcs.append(src)
                        if not srcs:
                            continue
                        src_nodata = float(BAND_SPECS[band].nodata)
                        merge_output = merge(
                            srcs, bounds=reproj_bounds, nodata=src_nodata
                        )
                        merged = merge_output[0]
                        transform = merge_output[1]
                        profile = {
                            "driver": "GTiff",
                            "height": merged.shape[1],
                            "width": merged.shape[2],
                            "count": 1,
                            "dtype": merged.dtype,
                            "crs": srcs[0].crs,
                            "transform": transform,
                            "nodata": src_nodata,
                        }
                        profile_transform: Any = profile.get("transform")
                        if profile_transform is None:
                            del merged
                            continue
                        prof_affine = (
                            profile_transform
                            if isinstance(profile_transform, Affine)
                            else Affine(*profile_transform)
                        )
                        if profile.get("crs") is None or prof_affine.almost_equals(
                            Affine.identity()
                        ):
                            del merged
                            continue
                        with MemoryFile() as mem:
                            with mem.open(**profile) as tmp:
                                tmp.write(merged[0], 1)
                                with warnings.catch_warnings():
                                    warnings.filterwarnings(
                                        "ignore", category=NotGeoreferencedWarning
                                    )
                                    mask_output = mask(
                                        tmp,
                                        [mapping(geom_proj)],
                                        crop=True,
                                        nodata=src_nodata,
                                    )
                                    clipped = mask_output[0]
                                    clipped_transform = mask_output[1]
                                clipped_profile = dict(tmp.profile)
                                clipped_profile.update(
                                    height=clipped.shape[1],
                                    width=clipped.shape[2],
                                    transform=clipped_transform,
                                    crs=tmp.crs,
                                    nodata=src_nodata,
                                )
                        with warnings.catch_warnings():
                            warnings.filterwarnings(
                                "ignore",
                                category=RuntimeWarning,
                            )
                            arr = clipped[0].astype("float32")
                        arr[arr == float(src_nodata)] = np.nan
                        arr *= float(BAND_SPECS[band].scale)
                        band_arrays[band] = arr
                        if profile_ref is None:
                            profile_ref = clipped_profile
                        del merged, clipped, arr
                    finally:
                        for src in opened_srcs:
                            src.close()
                if not band_arrays or profile_ref is None:
                    return None
                return RasterStackOutput(band_arrays=band_arrays, profile=profile_ref)

            return execute_with_retry(_task)

        def generate_indices(
            band_arrays: dict[str, np.ndarray],
        ) -> dict[str, np.ndarray]:
            out = {}
            if "NDVI" in band_arrays:
                out["NDVI"] = band_arrays["NDVI"].astype("float32")
            if "EVI" in band_arrays:
                out["EVI"] = band_arrays["EVI"].astype("float32")
            red = band_arrays.get("red_reflectance")
            nir = band_arrays.get("NIR_reflectance")
            mir = band_arrays.get("MIR_reflectance")
            savi_l = 0.5
            if red is not None and nir is not None:
                den = nir + red + savi_l
                out["SAVI"] = np.where(
                    np.abs(den) > 1e-6, ((nir - red) / den) * (1 + savi_l), np.nan
                ).astype("float32")
            if nir is not None and mir is not None:
                den = nir + mir
                out["NDWI"] = np.where(
                    np.abs(den) > 1e-6, (nir - mir) / den, np.nan
                ).astype("float32")
            return out

        def calculate_metrics(
            indices: dict[str, np.ndarray],
            profile: dict[str, Any],
            missing_munis: gpd.GeoDataFrame,
            obs_date: str,
            collection: str,
        ) -> CollectionMetrics:
            transform_val = profile.get("transform")
            crs_val = profile.get("crs")
            if transform_val is None or crs_val is None:
                return CollectionMetrics()
            prof_affine = (
                transform_val
                if isinstance(transform_val, Affine)
                else Affine(*transform_val)
            )
            if prof_affine.almost_equals(Affine.identity()):
                return CollectionMetrics()
            parsed_date = pd.to_datetime(obs_date).date()
            collection_metrics = CollectionMetrics()
            munis_proj = missing_munis.to_crs(crs_val)
            for attr, arr in indices.items():
                arr_calc = arr.astype("float32", copy=True)
                arr_calc[np.isnan(arr_calc)] = -9999.0
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", NotGeoreferencedWarning)
                    stats = zonal_stats(
                        munis_proj.geometry,
                        arr_calc,
                        affine=prof_affine,
                        nodata=-9999.0,
                        stats=[
                            "mean",
                            "std",
                            "median",
                            "percentile_25",
                            "percentile_75",
                            "min",
                            "max",
                        ],
                        all_touched=False,
                    )
                for (_, muni), stat in zip(missing_munis.iterrows(), stats):
                    collection_metrics.records.append(
                        MetricRecord(
                            date=parsed_date,
                            geocode=int(muni["geocode"]),
                            collection=collection,
                            attribute=attr,
                            mean=stat.get("mean"),
                            std=stat.get("std"),
                            median=stat.get("median"),
                            q25=stat.get("percentile_25"),
                            q75=stat.get("percentile_75"),
                            min=stat.get("min"),
                            max=stat.get("max"),
                        )
                    )
                del arr_calc
            return collection_metrics

        def get_missing_geocodes(
            database_uri: str,
            tablename: str,
            collection: str,
            obs_date: dt_date,
            all_geocodes: List[int],
        ) -> List[int]:
            if not all_geocodes:
                return []
            engine: Engine = create_engine(database_uri, pool_pre_ping=True)
            geocodes_tuple = tuple(all_geocodes)
            query = text(
                f"SELECT DISTINCT geocode FROM {tablename} WHERE date = :obs_date AND collection = :collection AND geocode IN :geocodes"
            )
            with engine.begin() as conn:
                existing_geocodes = {
                    int(row[0])
                    for row in conn.execute(
                        query,
                        {
                            "obs_date": obs_date,
                            "collection": collection,
                            "geocodes": geocodes_tuple,
                        },
                    ).fetchall()
                }
            engine.dispose()
            return [g for g in all_geocodes if g not in existing_geocodes]

        def insert_metric_records(
            database_uri: str, tablename: str, records: List[MetricRecord]
        ) -> int:
            if not records:
                return 0
            engine = create_engine(database_uri, pool_pre_ping=True)
            query = text(
                f"""
                INSERT INTO {tablename} (date, geocode, collection, attribute, mean, std, median, q25, q75, min, max)
                VALUES (:date, :geocode, :collection, :attribute, :mean, :std, :median, :q25, :q75, :min, :max)
                ON CONFLICT (date, geocode, collection, attribute)
                DO UPDATE SET
                    mean = EXCLUDED.mean, std = EXCLUDED.std, median = EXCLUDED.median,
                    q25 = EXCLUDED.q25, q75 = EXCLUDED.q75, min = EXCLUDED.min, max = EXCLUDED.max
            """
            )
            bind_params = [r.model_dump() for r in records]
            with engine.begin() as conn:
                result = conn.execute(query, bind_params)
                row_count = getattr(result, "rowcount", 0) or 0
            engine.dispose()
            return row_count

        logger.info(
            f"Starting pipeline execution for UF: {target_uf}. Window starting: {start_ds}"
        )

        collection = "myd13q1-6.1"
        schema_name = "vegetation_indices"
        table_base = "vegetation_index_metrics"
        tablename = f"{schema_name}.{table_base}" if schema_name else table_base

        muni_container = load_municipalities_optimized(grid_cache, target_uf=target_uf)
        processing_munis = muni_container.to_gdf()

        logger.info(f"Fetching STAC collection {collection} items")
        items = fetch_stac_range(collection, processing_munis, start_ds, end_ds)
        logger.info(f"Successfully fetched {len(items)} items from STAC")

        urls_by_date = defaultdict(lambda: defaultdict(list))
        for item in items:
            if item.datetime is None:
                continue
            obs_date = item.datetime.strftime("%Y-%m-%d")
            for band in BASE_BANDS:
                href = None
                for alias in BAND_SPECS[band].aliases:
                    if alias in item.assets:
                        href = str(item.assets[alias].href)
                        break
                if href:
                    urls_by_date[obs_date][band].append(href)

        urls_by_date_map = {d: dict(b) for d, b in urls_by_date.items()}
        if not urls_by_date_map:
            logger.warning(
                f"No matched STAC assets discovered for period {start_ds} to {end_ds}"
            )
            return

        for obs_date_key, band_urls in sorted(urls_by_date_map.items()):
            logger.info(f"Starting processing for observation date: {obs_date_key}")
            parsed_obs_date = pd.to_datetime(obs_date_key).date()
            missing_munis = processing_munis.copy()

            if database_uri:
                all_geocodes = processing_munis["geocode"].tolist()
                missing_geocodes = get_missing_geocodes(
                    database_uri, tablename, collection, parsed_obs_date, all_geocodes
                )
                missing_munis_sliced = processing_munis[
                    processing_munis["geocode"].isin(missing_geocodes)
                ].copy()
                assert isinstance(missing_munis_sliced, gpd.GeoDataFrame)
                missing_munis = missing_munis_sliced

            assert isinstance(missing_munis, gpd.GeoDataFrame)
            if missing_munis.empty:
                logger.info(
                    f"All geocodes in {target_uf} are already populated for date {obs_date_key}. Skipping raster processing."
                )
                continue

            logger.info(
                f"Geocodes missing metrics: {len(missing_munis)}. Beginning raster extraction."
            )
            bounds = tuple(missing_munis.to_crs(4326).total_bounds)
            geom = missing_munis.to_crs(4326).geometry.union_all()

            attributes = []
            if band_urls.get("NDVI"):
                attributes.append("NDVI")
            if band_urls.get("EVI"):
                attributes.append("EVI")
            if band_urls.get("red_reflectance") and band_urls.get("NIR_reflectance"):
                attributes.append("SAVI")
            if band_urls.get("NIR_reflectance") and band_urls.get("MIR_reflectance"):
                attributes.append("NDWI")

            bands_list = []
            if "NDVI" in attributes:
                bands_list.append("NDVI")
            if "EVI" in attributes:
                bands_list.append("EVI")
            if "SAVI" in attributes:
                bands_list.extend(["red_reflectance", "NIR_reflectance"])
            if "NDWI" in attributes:
                bands_list.extend(["NIR_reflectance", "MIR_reflectance"])
            required_bands = list(dict.fromkeys(bands_list))

            logger.info("Opening remote raster stack via GDAL memory mapping.")
            stack = open_raster_stack_in_memory(band_urls, bounds, geom, required_bands)
            if stack is None:
                logger.info(
                    f"Raster stack initialization returned empty bounds for {obs_date_key}"
                )
                continue

            band_arrays = stack.band_arrays
            profile = stack.profile
            logger.info("Generating vegetation indices.")
            indices = generate_indices(band_arrays)

            logger.info("Calculating zonal statistics.")
            metrics_container = calculate_metrics(
                indices, profile, missing_munis, obs_date_key, collection
            )

            if not metrics_container.is_empty and database_uri:
                logger.info(
                    f"Persisting {len(metrics_container.records)} computed records to database."
                )
                rows_modified = insert_metric_records(
                    database_uri, tablename, metrics_container.records
                )
                logger.info(
                    f"Database transaction complete. Rows modified: {rows_modified}"
                )

            del band_arrays, indices, stack
            gc.collect()

        logger.info(f"Pipeline module successfully completed for target {target_uf}")

    run_state_pipeline.partial(
        base_date="{{ ds }}",
        database_uri=uri["PSQL_MAIN_URI"],
        grid_cache="cache/municipios_br_2020.gpkg",
    ).expand(target_uf=BRAZIL_STATES)
