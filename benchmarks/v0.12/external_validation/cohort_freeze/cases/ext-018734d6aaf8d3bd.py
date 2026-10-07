def cors(*methods: str) -> Callable[[ViewFunc], ViewFunc]:
    methods_set = set(methods)
    methods_set.add("OPTIONS")
    methods_str = ", ".join(methods_set)

    def decorator(f: ViewFunc) -> ViewFunc:
        @wraps(f)
        def wrapper(request: HttpRequest, *args: Any, **kwds: Any) -> HttpResponse:
            if request.method == "OPTIONS":
                # Handle OPTIONS here
                response = HttpResponse(status=204)
            elif request.method in methods:
                response = f(request, *args, **kwds)
            else:
                response = HttpResponse(status=405)

            response["Access-Control-Allow-Origin"] = "*"
            response["Access-Control-Allow-Headers"] = "X-Api-Key"
            response["Access-Control-Allow-Methods"] = methods_str
            response["Access-Control-Max-Age"] = "600"
            return response

        return wrapper

    return decorator
