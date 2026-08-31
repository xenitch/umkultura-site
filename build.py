#!/usr/bin/env python3
"""Сборка сайта: content/ + templates/ + афиша -> docs/."""
from datetime import date
from pathlib import Path, PurePosixPath
import shutil
import sys

import frontmatter
import markdown
from jinja2 import Environment, FileSystemLoader

import afisha
import library

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


def build(root: Path, today=None, fetch=afisha.fetch_csv,
          cover_fetch=None) -> None:
    if cover_fetch is None:
        cover_fetch = library.fetch_cover
    today = today or date.today()
    content_dir, out = root / "content", root / "docs"
    lib_dir = content_dir / "bookclubs" / "library"

    events = afisha.load_events(fetch(root / "data" / "afisha.csv"))
    upcoming, past = afisha.split_events(events, today)
    books = library.group_books(past)
    for b in books:
        cover = cover_fetch(b.cover_url, b.slug, root / "static" / "covers")
        b.cover_file = f"/static/covers/{cover.name}" if cover else ""
        b.clubs_caption = library.clubs_caption(b)
        ann = lib_dir / f"{b.slug}.md"
        if ann.exists():
            post = frontmatter.load(ann)
            b.title = post.metadata.get("title", b.title)
            b.author = post.metadata.get("author", b.author)
            b.about = render_md(post.content)
        else:
            print(f"⚠ нет аннотации: {b.slug}", file=sys.stderr)

    ctx = {
        "site": SITE,
        "schedule_groups": afisha.group_schedule(upcoming, today),
        "showcase_groups": library.group_showcase(books, today),
        "library_counter": library.counter_text(len(books)),
    }

    env = Environment(loader=FileSystemLoader(root / "templates"), autoescape=False)
    pages = [load_page(p, content_dir) for p in sorted(content_dir.rglob("*.md"))
             if not (p.parent == lib_dir and p.name != "index.md")]

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

    for b in books:
        page = {"url": f"/bookclubs/library/{b.slug}/",
                "meta": {"title": b.title,
                         "description": f"{b.title} — обсуждения в книжных клубах Кемерова"},
                "content": ""}
        discussions = [{"date": library.discussion_date(d), "club": d.club,
                        "contact": d.contact, "summary": d.summary,
                        "review_url": d.review_url} for d in b.discussions]
        html = env.get_template("book.html").render(
            page=page, book=b, discussions=discussions, **ctx)
        dest = out / page["url"].strip("/") / "index.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    build(Path(__file__).parent)
    print("Собрано в docs/")
