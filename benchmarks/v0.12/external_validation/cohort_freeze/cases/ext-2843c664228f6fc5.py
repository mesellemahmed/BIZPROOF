def _generate_shipping_method_payload(shipping_method, channel):
    if not shipping_method:
        return None

    shipping_method_channel_listing = shipping_method.channel_listings.filter(
        channel=channel,
    ).first()

    if not shipping_method_channel_listing:
        return None

    serializer = PayloadSerializer()
    shipping_method_fields = ("name", "type")

    payload = serializer.serialize(
        [shipping_method],
        fields=shipping_method_fields,
        extra_dict_data={
            "currency": shipping_method_channel_listing.currency,
            "price_amount": quantize_price(
                shipping_method_channel_listing.price_amount,
                shipping_method_channel_listing.currency,
            ),
        },
    )

    return json.loads(payload)[0]
