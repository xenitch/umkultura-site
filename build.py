#!/usr/bin/env python3
"""Сборка сайта: content/ + templates/ + афиша -> docs/."""
from datetime import date
from pathlib import Path, PurePosixPath
import shutil

import frontmatter
import markdown
from jinja2 import Environment, FileSystemLoader

import afisha

SITE = {
    "name": "Пространство развития умственной культуры",
    "domain": "umkultura.ru",
    "author": "Ксения Костюченко",
    "description": ("Городская афиша книжных клубов Кемерова: "
                    "будущие чтения и библиотека прошедших обсуждений."),
}


def page_url(rel: PurePosixPath) -> str:
    parts = rel.parent.parts if rel.name == "index.md" else rel.parent.parts + (rel.stem,)
    return "/" + "/".join(parts) + "/" if parts else "/"


def render_md(text: str) -> str:
    return markdown.markdown(text, extensions=["extra"])


def load_page(path: Path, content_dir: Path) -> dict:
    post = frontmatter.load(path)
    rel = PurePosixPath(path.relative_to(content_dir).as_posix())
    return {"url": page_url(rel), "meta": post.metadata,
            "content": render_md(post.content)}


def build(root: Path, today=None, fetch=afisha.fetch_csv) -> None:
    today = today or date.today()
    content_dir, out = root / "content", root / "docs"

    events = afisha.load_events(fetch(root / "data" / "afisha.csv"))
    upcoming, past = afisha.split_events(events, today)
    ctx = {
        "site": SITE,
        "schedule_groups": afisha.group_schedule(upcoming, today),
        "archive_years": afisha.group_archive(past),
    }

    env = Environment(loader=FileSystemLoader(root / "templates"), autoescape=False)
    pages = [load_page(p, content_dir) for p in sorted(content_dir.rglob("*.md"))]

    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(root / "static", out / "static")
    (out / "CNAME").write_text(SITE["domain"], encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")

    for page in pages:
        tpl = page["meta"].get("template") or "page.html"
        html = env.get_template(tpl).render(page=page, **ctx)
        dest = out / page["url"].strip("/") / "index.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    build(Path(__file__).parent)
    print("Собрано в docs/")
