def __str__(self):
    return mark_safe(self.__html__())  # noqa: S308 - flatatt-rendered attributes are escaped
