BEGIN;
CREATE SCHEMA IF NOT EXISTS f1;
CREATE TABLE IF NOT EXISTS f1.circuits (
 circuit_id TEXT PRIMARY KEY, name TEXT NOT NULL, country TEXT, locality TEXT,
 latitude DOUBLE PRECISION CHECK(latitude BETWEEN -90 AND 90),
 longitude DOUBLE PRECISION CHECK(longitude BETWEEN -180 AND 180));
CREATE TABLE IF NOT EXISTS f1.drivers (
 driver_id TEXT PRIMARY KEY, given_name TEXT NOT NULL, family_name TEXT NOT NULL,
 birth_date DATE, nationality TEXT);
CREATE TABLE IF NOT EXISTS f1.constructors (
 constructor_id TEXT PRIMARY KEY, name TEXT NOT NULL, nationality TEXT);
CREATE TABLE IF NOT EXISTS f1.races (
 season INTEGER NOT NULL CHECK(season>=1950), round INTEGER NOT NULL CHECK(round>0),
 circuit_id TEXT NOT NULL REFERENCES f1.circuits, name TEXT NOT NULL,
 race_date DATE NOT NULL, starts_at TIMESTAMPTZ,
 PRIMARY KEY(season,round));
CREATE TABLE IF NOT EXISTS f1.results (
 season INTEGER NOT NULL, round INTEGER NOT NULL,
 driver_id TEXT NOT NULL REFERENCES f1.drivers,
 constructor_id TEXT NOT NULL REFERENCES f1.constructors,
 grid INTEGER CHECK(grid>=0), position INTEGER CHECK(position>0),
 points NUMERIC(8,2) CHECK(points>=0), laps INTEGER CHECK(laps>=0), status TEXT,
 loaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(season,round,driver_id),
 FOREIGN KEY(season,round) REFERENCES f1.races);
CREATE TABLE IF NOT EXISTS f1.sprint_results (LIKE f1.results INCLUDING DEFAULTS INCLUDING CONSTRAINTS,
 PRIMARY KEY(season,round,driver_id),
 FOREIGN KEY(season,round) REFERENCES f1.races,
 FOREIGN KEY(driver_id) REFERENCES f1.drivers,
 FOREIGN KEY(constructor_id) REFERENCES f1.constructors);
CREATE TABLE IF NOT EXISTS f1.qualifying (
 season INTEGER NOT NULL, round INTEGER NOT NULL,
 driver_id TEXT NOT NULL REFERENCES f1.drivers,
 constructor_id TEXT NOT NULL REFERENCES f1.constructors,
 position INTEGER CHECK(position>0),
 q1_seconds NUMERIC(10,3) CHECK(q1_seconds>0),
 q2_seconds NUMERIC(10,3) CHECK(q2_seconds>0),
 q3_seconds NUMERIC(10,3) CHECK(q3_seconds>0),
 PRIMARY KEY(season,round,driver_id), FOREIGN KEY(season,round) REFERENCES f1.races);
CREATE TABLE IF NOT EXISTS f1.driver_standings (
 season INTEGER NOT NULL, round INTEGER NOT NULL,
 driver_id TEXT NOT NULL REFERENCES f1.drivers,
 position INTEGER CHECK(position>0), points NUMERIC(10,2), wins INTEGER CHECK(wins>=0),
 PRIMARY KEY(season,round,driver_id), FOREIGN KEY(season,round) REFERENCES f1.races);
CREATE TABLE IF NOT EXISTS f1.constructor_standings (
 season INTEGER NOT NULL, round INTEGER NOT NULL,
 constructor_id TEXT NOT NULL REFERENCES f1.constructors,
 position INTEGER CHECK(position>0), points NUMERIC(10,2), wins INTEGER CHECK(wins>=0),
 PRIMARY KEY(season,round,constructor_id), FOREIGN KEY(season,round) REFERENCES f1.races);
CREATE TABLE IF NOT EXISTS f1.model_versions (
 model_version TEXT PRIMARY KEY, target TEXT NOT NULL CHECK(target IN ('win','podium','dnf')),
 trained_at TIMESTAMPTZ NOT NULL, training_cutoff TIMESTAMPTZ NOT NULL,
 metrics JSONB NOT NULL DEFAULT '{}', UNIQUE(model_version,target),
 CHECK(training_cutoff<=trained_at));
CREATE TABLE IF NOT EXISTS f1.predictions (
 prediction_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 season INTEGER NOT NULL, round INTEGER NOT NULL, driver_id TEXT NOT NULL REFERENCES f1.drivers,
 target TEXT NOT NULL, model_version TEXT NOT NULL,
 probability DOUBLE PRECISION NOT NULL CHECK(probability BETWEEN 0 AND 1),
 generated_at TIMESTAMPTZ NOT NULL, feature_cutoff TIMESTAMPTZ NOT NULL,
 explanation JSONB, FOREIGN KEY(season,round) REFERENCES f1.races,
 FOREIGN KEY(model_version,target) REFERENCES f1.model_versions(model_version,target),
 UNIQUE(season,round,driver_id,target,model_version,generated_at),
 CHECK(feature_cutoff<=generated_at));
CREATE TABLE IF NOT EXISTS f1.etl_runs (
 run_id TEXT PRIMARY KEY, season INTEGER CHECK(season>=1950),
 started_at TIMESTAMPTZ NOT NULL, finished_at TIMESTAMPTZ,
 status TEXT NOT NULL CHECK(status IN ('running','success','partial','failed')),
 records_count INTEGER NOT NULL DEFAULT 0 CHECK(records_count>=0),
 rejected_count INTEGER NOT NULL DEFAULT 0 CHECK(rejected_count>=0), error_summary TEXT,
 CHECK(finished_at IS NULL OR finished_at>=started_at));
CREATE INDEX IF NOT EXISTS results_driver_idx ON f1.results(driver_id,season,round);
CREATE INDEX IF NOT EXISTS results_constructor_idx ON f1.results(constructor_id,season,round);
CREATE INDEX IF NOT EXISTS predictions_lookup_idx ON f1.predictions(season,round,target,generated_at DESC);
COMMIT;
