Release Notes
---

## [1.2.0](https://github.com/AlertaDengue/AlertFlow/compare/1.1.2...1.2.0) (2023-05-18)


### Features

* Add conditional secrets export based on repository type ([b007445](https://github.com/AlertaDengue/AlertFlow/commit/b00744520b184966955b1212af66beac85ab691e))
* **dags:** Add EPISCANNER_EXPORT_DATA DAG ([afc063b](https://github.com/AlertaDengue/AlertFlow/commit/afc063b527ba48da0fb75f6ae2412fce8ad7773a))
* **docker:** Add user with passed UID/GID ([d149995](https://github.com/AlertaDengue/AlertFlow/commit/d1499954deb06e6c79aad25fb4385c95776d8ed3))
* **docker:** Set host user and group IDs for Airflow container ([3ae36ed](https://github.com/AlertaDengue/AlertFlow/commit/3ae36edbf80a7290e66b9dc370437039e32de648))
* Update Episcanner-Downloader DAG with Improved PSQL Connection and Schedule ([#25](https://github.com/AlertaDengue/AlertFlow/issues/25)) ([e9cbbf4](https://github.com/AlertaDengue/AlertFlow/commit/e9cbbf462118e68954b4e4b7b12b199524305e79))

## [1.1.2](https://github.com/AlertaDengue/AlertFlow/compare/1.1.1...1.1.2) (2023-04-13)


### Bug Fixes

* **satellite:** create satellite environment w/ py3.10 ([#17](https://github.com/AlertaDengue/AlertFlow/issues/17)) ([5e7ef86](https://github.com/AlertaDengue/AlertFlow/commit/5e7ef8658366328785f51a939630d529868d740e))

## [1.1.1](https://github.com/AlertaDengue/AlertFlow/compare/1.1.0...1.1.1) (2023-04-11)


### Bug Fixes

* **containers:** rolling back to a short system ([#15](https://github.com/AlertaDengue/AlertFlow/issues/15)) ([5a15b22](https://github.com/AlertaDengue/AlertFlow/commit/5a15b226131d1fae029f0d138738d9b194a5095a))
* **release:** fix semantic-release ([#16](https://github.com/AlertaDengue/AlertFlow/issues/16)) ([fccdd71](https://github.com/AlertaDengue/AlertFlow/commit/fccdd715c5c9cac4e7de668e32444d81a9b22d01))

## [1.1.0](https://github.com/AlertaDengue/AlertFlow/compare/1.0.0...1.1.0) (2023-03-17)


### Features

* **satellite:** copernicus satellite DAGS ([#8](https://github.com/AlertaDengue/AlertFlow/issues/8)) ([ca5f098](https://github.com/AlertaDengue/AlertFlow/commit/ca5f098442bac0cac17c4be3591747ee96ac62f0))


### Bug Fixes

* **cope:** fiz foz DAG ([#12](https://github.com/AlertaDengue/AlertFlow/issues/12)) ([28e44ed](https://github.com/AlertaDengue/AlertFlow/commit/28e44edb13335f3a8bb262b305299a1db0a1cd92))
* **docker:** Fix non-root access to volume directories ([#9](https://github.com/AlertaDengue/AlertFlow/issues/9)) ([ea7ad42](https://github.com/AlertaDengue/AlertFlow/commit/ea7ad4279608ca5982900b6214377f3db103e5b1))

## 1.0.0 (2023-02-21)


### Features

* **ci:** pr title linter ([21a4e0a](https://github.com/luabida/AlertFlow/commit/21a4e0ada62720638d27de8d546335a44331aa77))


### Bug Fixes

* **ci:** quotes ([bc7c44e](https://github.com/luabida/AlertFlow/commit/bc7c44e9e7a5f0576cd01eb9d0b7264d74d593c1))
