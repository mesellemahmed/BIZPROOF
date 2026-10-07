def get_variants_stocks(
    self,
    site,
    variant_data_list: list[tuple[VARIANT_ID, CHANNEL_SLUG, COUNTRY_CODE]],
) -> Promise[list[Iterable[Stock]]]:
    calculate_stocks_with_shipping_zones = (
        site.settings.use_legacy_shipping_zone_stock_availability
    )
    if calculate_stocks_with_shipping_zones:
        return StocksWithAvailableQuantityByProductVariantIdCountryCodeAndChannelLoader(
            self.context
        ).load_many(
            [
                (variant_id, country_code, channel_slug)
                for variant_id, channel_slug, country_code in variant_data_list
            ]
        )
    return StocksWithAvailableQuantityByProductVariantIdAndChannelSlugLoader(
        self.context
    ).load_many(
        [
            (variant_id, channel_slug)
            for variant_id, channel_slug, _country_code in variant_data_list
        ]
    )
