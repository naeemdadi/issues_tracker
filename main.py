from fastapi import FastAPI

from routers import auth, comments, issues, labels, members, projects

# Tables are managed by Alembic: run `alembic upgrade head` before starting.
app = FastAPI()

for router_module in (auth, projects, members, labels, issues, comments):
    app.include_router(router_module.router)
