def get_volume_type_encryption_link(volume_type):
    if _does_vol_type_enc_exist(volume_type):
        return reverse("horizon:admin:volume_types:type_encryption_detail",
                       kwargs={'volume_type_id': volume_type.id})
