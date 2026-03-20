# Blog App

A fully working Flask blog with SQLite database, login, posts, comments, and tags.
Zero config required — runs out of the box.

## Run in 3 commands

```bash
cd blog-app
pip install -r requirements.txt
python app.py
```

Then open http://localhost:5000

## Demo account
- Email:    demo@example.com
- Password: password123

## Features
- Register / login / logout
- Create, edit, delete posts (draft or published)
- Comment on posts, delete your own comments
- Tag filtering
- Pagination (5 posts per page)
- SQLite database (no setup, file created automatically)
- /health endpoint

## Switch to PostgreSQL
Set the DATABASE_URL environment variable:

```bash
export DATABASE_URL="postgresql://user:password@localhost:5432/blogdb"
python app.py
```
