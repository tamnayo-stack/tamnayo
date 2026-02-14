def render_template(body: str, context: dict[str, str]) -> str:
    rendered = body
    for key in ["매장명", "플랫폼", "고객명", "메뉴"]:
        rendered = rendered.replace(f"{{{key}}}", context.get(key, "") or "")
    return rendered
