from __future__ import annotations

import calendar
import gc
import logging
import time
import warnings
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Callable, TypeVar
from typing_extensions import Annotated

import geobr
import geopandas as gpd
import numpy as np
import pandas as pd
import pystac_client
import rasterio
from affine import Affine
from pydantic import BaseModel, ConfigDict, Field, BeforeValidator
from rasterio.errors import NotGeoreferencedWarning
from rasterio.io import MemoryFile
from rasterio.mask import mask
from rasterio.merge import merge
from rasterio.warp import transform_bounds
from rasterstats import zonal_stats
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry
from sqlalchemy import (
    Column,
    Date,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    create_engine,
    select,
)
from sqlalchemy.dialects.postgresql import insert

STAC_URL = "https://data.inpe.br/bdc/stac/v1/"
DEFAULT_COLLECTION = "myd13q1-6.1"
DEFAULT_TABLE = "vegetation_index_metrics"
DEFAULT_METADATA = MetaData()
DEFAULT_GRID_CACHE = "cache/municipios_br_2020.gpkg"
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 2.0

SAVI_L = 0.5
TMP_NODATA = -9999.0

BAND_SPECS = {
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

BASE_BANDS = list(BAND_SPECS)

TABLE = Table(
    DEFAULT_TABLE,
    DEFAULT_METADATA,
    Column("date", Date, nullable=False),
    Column("geocode", Integer, nullable=False),
    Column("collection", String(64), nullable=False),
    Column("attribute", String(64), nullable=False),
    Column("mean", Float),
    Column("std", Float),
    Column("median", Float),
    Column("q25", Float),
    Column("q75", Float),
    Column("min", Float),
    Column("max", Float),
    UniqueConstraint(
        "date",
        "geocode",
        "collection",
        "attribute",
        name="uq_vi_metrics",
    ),
)

logger = logging.getLogger(__name__)
T = TypeVar("T")

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

warnings.filterwarnings(
    "ignore", category=NotGeoreferencedWarning, module="rasterio.features"
)
warnings.filterwarnings(
    "ignore", category=NotGeoreferencedWarning, module="rasterstats"
)


def num_to_none(v: Any) -> Any:
    if v is None:
        return None
    try:
        if np.isnan(v):
            return None
    except TypeError:
        pass
    return v


CleanFloat = Annotated[float | None, BeforeValidator(num_to_none)]


class MetricRecord(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    date: date
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
            return gpd.GeoDataFrame(columns=["geocode", "uf", "geometry"], crs=self.crs)
        data = [
            {"geocode": m.geocode, "uf": m.uf, "geometry": m.geometry}
            for m in self.municipalities
        ]
        return gpd.GeoDataFrame(data, crs=self.crs)


def execute_with_retry(
    operation: Callable[[], T],
    description: str,
    attempts: int = DEFAULT_RETRY_ATTEMPTS,
    backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
) -> T:
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except Exception as exc:
            if attempt >= attempts:
                logger.error(
                    "%s failed after %s attempts: %s", description, attempts, exc
                )
                raise
            wait_time = backoff_seconds * (2 ** (attempt - 1))
            logger.warning(
                "%s failed on attempt %s/%s: %s. Retrying in %.1fs.",
                description,
                attempt,
                attempts,
                exc,
                wait_time,
            )
            time.sleep(wait_time)
    raise RuntimeError(f"{description} failed without an explicit exception.")


def load_municipalities_optimized(
    grid_cache: str, geocodes: list[int] | None = None
) -> MunicipalityCollection:
    path = Path(grid_cache)
    if not path.exists():
        logger.info("Downloading municipality mesh via geobr to initialize cache.")
        path.parent.mkdir(parents=True, exist_ok=True)
        munis = geobr.read_municipality(year=2020)
        munis.to_file(path, driver="GPKG")

    if geocodes:
        geocodes_str = ",".join(str(g) for g in geocodes)
        sql = f"SELECT * FROM municipios_br_2020 WHERE code_muni IN ({geocodes_str})"
        munis = gpd.read_file(path, sql=sql)
    else:
        logger.info("Loading complete mesh from cache.")
        munis = gpd.read_file(path)

    munis = munis.copy()
    munis["geocode"] = munis["code_muni"].astype(int)
    munis["uf"] = munis["abbrev_state"].str.upper()

    records = []
    for row in munis.itertuples():
        records.append(
            MunicipalityGeoRecord(
                geocode=int(row.geocode),
                uf=str(row.uf),
                geometry=row.geometry,
            )
        )

    return MunicipalityCollection(municipalities=records, crs=munis.crs)


def fetch_stac_items(
    collection: str, state_munis: gpd.GeoDataFrame, year: int, month: int
):
    if not 1 <= month <= 12:
        raise ValueError("Month must be between 1 and 12.")
    _, last_day = calendar.monthrange(year, month)
    stac_period = f"{year}-{month:02d}-01/{year}-{month:02d}-{last_day:02d}"

    kwargs = {
        "collections": [collection],
        "bbox": tuple(state_munis.to_crs(4326).total_bounds),
        "datetime": stac_period,
    }

    def fetch():
        client = pystac_client.Client.open(STAC_URL)
        search = client.search(**kwargs)
        return sorted(list(search.items()), key=lambda item: item.datetime)

    return execute_with_retry(
        fetch, f"Fetch STAC collection={collection} year={year} month={month}"
    )


def open_raster_stack_in_memory(
    urls_by_band: dict[str, list[str]], state_bounds, state_geom, bands: list[str]
):
    def _task():
        first_band = next((band for band in bands if urls_by_band.get(band)), None)
        if not first_band:
            return None

        with rasterio.open(urls_by_band[first_band][0]) as first_src:
            first_affine = (
                first_src.transform
                if isinstance(first_src.transform, Affine)
                else Affine(*first_src.transform)
            )
            if first_src.crs is None or first_affine.almost_equals(Affine.identity()):
                return None
            raster_crs = first_src.crs
            reproj_bounds = transform_bounds(
                "EPSG:4326", raster_crs, *state_bounds, densify_pts=21
            )
            geom_proj = gpd.GeoSeries([state_geom], crs=4326).to_crs(raster_crs).iloc[0]

        band_arrays: dict[str, np.ndarray] = {}
        profile_ref = None

        for band in bands:
            urls = urls_by_band.get(band, [])
            if not urls:
                continue
            opened_srcs = [rasterio.open(url) for url in urls]

            try:
                srcs = []
                for src in opened_srcs:
                    src_affine = (
                        src.transform
                        if isinstance(src.transform, Affine)
                        else Affine(*src.transform)
                    )
                    if src.crs is None or src_affine.almost_equals(Affine.identity()):
                        continue
                    if not (
                        src.bounds.right <= reproj_bounds[0]
                        or src.bounds.left >= reproj_bounds[2]
                        or src.bounds.top <= reproj_bounds[1]
                        or src.bounds.bottom >= reproj_bounds[3]
                    ):
                        srcs.append(src)

                if not srcs:
                    continue
                src_nodata = BAND_SPECS[band]["nodata"]
                merged, transform = merge(srcs, bounds=reproj_bounds, nodata=src_nodata)

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

                prof_affine = (
                    profile.get("transform")
                    if isinstance(profile.get("transform"), Affine)
                    else Affine(*profile.get("transform"))
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
                            clipped, clipped_transform = mask(
                                tmp, [mapping(geom_proj)], crop=True, nodata=src_nodata
                            )

                        clipped_profile = tmp.profile.copy()
                        clipped_profile.update(
                            height=clipped.shape[1],
                            width=clipped.shape[2],
                            transform=clipped_transform,
                            crs=tmp.crs,
                            nodata=src_nodata,
                        )

                arr = clipped[0].astype("float32")
                arr[arr == float(src_nodata)] = np.nan
                arr *= float(BAND_SPECS[band]["scale"])

                band_arrays[band] = arr
                if profile_ref is None:
                    profile_ref = clipped_profile
                del merged, clipped, arr
            finally:
                for src in opened_srcs:
                    src.close()

        return (
            None
            if not band_arrays or profile_ref is None
            else (band_arrays, profile_ref)
        )

    return execute_with_retry(_task, "Open COG stack in memory")


def generate_indices(band_arrays: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    if "NDVI" in band_arrays:
        out["NDVI"] = band_arrays["NDVI"].astype("float32")
    if "EVI" in band_arrays:
        out["EVI"] = band_arrays["EVI"].astype("float32")

    red = band_arrays.get("red_reflectance")
    nir = band_arrays.get("NIR_reflectance")
    mir = band_arrays.get("MIR_reflectance")

    if red is not None and nir is not None:
        den = nir + red + SAVI_L
        out["SAVI"] = np.where(
            np.abs(den) > 1e-6, ((nir - red) / den) * (1 + SAVI_L), np.nan
        ).astype("float32")

    if nir is not None and mir is not None:
        den = nir + mir
        out["NDWI"] = np.where(np.abs(den) > 1e-6, (nir - mir) / den, np.nan).astype(
            "float32"
        )
    return out


def calculate_metrics(
    indices: dict[str, np.ndarray],
    profile: dict,
    missing_munis: gpd.GeoDataFrame,
    obs_date: str,
    collection: str,
) -> CollectionMetrics:
    prof_affine = (
        profile.get("transform")
        if isinstance(profile.get("transform"), Affine)
        else Affine(*profile.get("transform"))
    )
    if profile.get("crs") is None or prof_affine.almost_equals(Affine.identity()):
        return CollectionMetrics()

    parsed_date = pd.to_datetime(obs_date).date()
    collection_metrics = CollectionMetrics()
    munis_proj = missing_munis.to_crs(profile["crs"])

    for attr, arr in indices.items():
        arr_calc = arr.astype("float32", copy=True)
        arr_calc[np.isnan(arr_calc)] = TMP_NODATA

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", NotGeoreferencedWarning)
            stats = zonal_stats(
                munis_proj.geometry,
                arr_calc,
                affine=prof_affine,
                nodata=TMP_NODATA,
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

        for muni, stat in zip(missing_munis.itertuples(), stats):
            collection_metrics.records.append(
                MetricRecord(
                    date=parsed_date,
                    geocode=int(muni.geocode),
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


def pipeline(
    database_uri: str,
    year: int,
    month: int,
    selected_geocodes: list[int],
    collection: str = DEFAULT_COLLECTION,
    grid_cache: str = DEFAULT_GRID_CACHE,
) -> int:
    try:
        engine = create_engine(database_uri, pool_pre_ping=True)

        stmt_existing = select(TABLE.c.geocode).where(
            TABLE.c.collection == collection,
            TABLE.c.geocode.in_(selected_geocodes),
            TABLE.c.date >= date(year, month, 1),
            TABLE.c.date <= date(year, month, calendar.monthrange(year, month)[1]),
        )

        with engine.begin() as conn:
            completed = {row[0] for row in conn.execute(stmt_existing).fetchall()}

        geocodes = set(selected_geocodes)
        missing_geocodes = list(geocodes - completed)

        if not missing_geocodes:
            logger.info(
                "All %s submitted municipalities already have data saved for %s/%s.",
                len(selected_geocodes),
                month,
                year,
            )
            engine.dispose()
            return 0

        logger.info(
            "Processing cities batch: %s pending out of %s submitted.",
            len(missing_geocodes),
            len(selected_geocodes),
        )

        muni_container = load_municipalities_optimized(
            grid_cache, geocodes=missing_geocodes
        )
        processing_munis = muni_container.to_gdf()

        items = fetch_stac_items(collection, processing_munis, year, month)

        urls_by_date = defaultdict(lambda: defaultdict(list))

        for item in items:
            obs_date = item.datetime.strftime("%Y-%m-%d")
            for band in BASE_BANDS:
                href = None
                for alias in BAND_SPECS[band]["aliases"]:
                    if alias in item.assets:
                        href = item.assets[alias].href
                        break
                if href:
                    urls_by_date[obs_date][band].append(href)

        urls_by_date = {d: dict(b) for d, b in urls_by_date.items()}

        if not urls_by_date:
            logger.warning(
                "No images found in STAC for the period %s/%s in this batch.",
                month,
                year,
            )
            engine.dispose()
            return 0

        total_modified = 0

        for obs_date, band_urls in sorted(urls_by_date.items()):
            logger.info("Processing observation date: %s", obs_date)

            bounds = tuple(processing_munis.to_crs(4326).total_bounds)
            geom = processing_munis.to_crs(4326).geometry.union_all()

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

            stack = open_raster_stack_in_memory(band_urls, bounds, geom, required_bands)

            if stack is None:
                continue

            band_arrays, profile = stack
            indices = generate_indices(band_arrays)

            for city in processing_munis.itertuples():
                single_muni_gdf = processing_munis[
                    processing_munis["geocode"] == city.geocode
                ].copy()

                metrics_container = calculate_metrics(
                    indices, profile, single_muni_gdf, obs_date, collection
                )

                if not metrics_container.is_empty:
                    records = [rec.model_dump() for rec in metrics_container.records]
                    with engine.begin() as conn:
                        stmt = insert(TABLE).values(records)
                        stmt = stmt.on_conflict_do_update(
                            index_elements=[
                                "date",
                                "geocode",
                                "collection",
                                "attribute",
                            ],
                            set_={
                                "mean": stmt.excluded["mean"],
                                "std": stmt.excluded["std"],
                                "median": stmt.excluded["median"],
                                "q25": stmt.excluded["q25"],
                                "q75": stmt.excluded["q75"],
                                "min": stmt.excluded["min"],
                                "max": stmt.excluded["max"],
                            },
                        )
                        total_modified += conn.execute(stmt).rowcount or 0

            del band_arrays, indices, stack
            gc.collect()

        logger.info(
            "Pipeline successfully finalized. Modified rows: %s",
            total_modified,
        )
        engine.dispose()
        return 0

    except Exception:
        logger.exception("Critical failure in differential pipeline processing.")
        return 1

