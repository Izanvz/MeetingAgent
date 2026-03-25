from fastapi import APIRouter, Depends, HTTPException
from src.api.models import ActionItemResponse, UpdateTaskRequest
from src.api.deps import get_db
from src.db.sqlite import Database

router = APIRouter()


@router.get("/tasks", response_model=list[ActionItemResponse])
def list_tasks(status: str | None = None, owner: str | None = None,
               db: Database = Depends(get_db)):
    return db.list_action_items(status=status, owner=owner)


@router.patch("/tasks/{task_id}", response_model=ActionItemResponse)
def update_task(task_id: str, body: UpdateTaskRequest, db: Database = Depends(get_db)):
    item = db.get_action_item(task_id)
    if not item:
        raise HTTPException(status_code=404, detail="Task not found")
    db.update_action_item_status(task_id, body.status)
    return db.get_action_item(task_id)
