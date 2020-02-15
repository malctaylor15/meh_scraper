-- sqlite3 data/meh_scraper.db
-- sqlite3 data/meh_scraper_qa.db

-- drop table if exists raw_response_backup;

create table if not exists raw_response_backup (
date TEXT,
raw_response TEXT
);

  -- drop table if exists raw_site_backup;

create table if not exists raw_site_community_stats (
date TEXT,
time TEXT,
raw_site TEXT
);
