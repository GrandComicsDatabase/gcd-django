RENAME TABLE
    stddata_country TO gcd_country,
    stddata_language TO gcd_language,    
    indexer_indexer TO gcd_indexer,
    indexer_imp_grant TO gcd_imp_grant,
    indexer_error TO gcd_error,
    legacy_migration_story_status TO gcd_migration_story_status,
    legacy_reservation TO gcd_reservation,
    legacy_series_indexers TO gcd_series_indexers,
    stats_count_stats TO gcd_count_stats,
    stats_recent_indexed_issue TO gcd_recent_indexed_issue,
    stats_download TO oi_download;
