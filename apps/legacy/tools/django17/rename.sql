RENAME TABLE
    gcd_country TO stddata_country,
    gcd_language TO stddata_language,    
    gcd_indexer TO indexer_indexer,
    gcd_imp_grant TO indexer_imp_grant,
    gcd_error TO indexer_error,
    gcd_migration_story_status TO legacy_migration_story_status,
    gcd_reservation TO legacy_reservation,
    gcd_series_indexers TO legacy_series_indexers,
    gcd_count_stats TO stats_count_stats,
    gcd_recent_indexed_issue TO stats_recent_indexed_issue,
    oi_download TO stats_download;
