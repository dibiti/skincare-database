-- db_config/migrations/V003__cosing_enrichment.sql
--
-- Columns for the CosIng enrichment step (Sprint 3).
-- CosIng is the European Commission's official cosmetic ingredient database;
-- we query its public search API once per ingredient and store the answer.

-- Official chemical identifiers, straight from CosIng.
-- 255, not 50: polymer families like CARBOMER carry several CAS numbers
-- joined together ('9007-20-9 / 9003-01-4 / ...').
ALTER TABLE ingredients ADD COLUMN cas_no VARCHAR(255);
ALTER TABLE ingredients ADD COLUMN ec_no VARCHAR(255);

-- For ingredients on a regulatory annex, the legal maximum concentration
-- (e.g. '0.3%' for Chlorphenesin, Annex V ref 50).
ALTER TABLE ingredients ADD COLUMN annex_max_concentration VARCHAR(100);

-- Enrichment bookkeeping: the database itself is the cache.
-- status: NULL = never queried | 'matched' | 'not_found'
-- Tracking 'not_found' matters: without it, every run would re-query the
-- same unmatchable names (trade names, typos) forever.
ALTER TABLE ingredients ADD COLUMN cosing_status VARCHAR(20);
ALTER TABLE ingredients ADD COLUMN cosing_checked_at TIMESTAMPTZ;
