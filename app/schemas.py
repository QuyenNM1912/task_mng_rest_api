from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Literal, Optional


# Auth

class UserRegister(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# Tasks

class TaskCreate(BaseModel):
    title: str
    status: Literal["todo", "doing", "done"] = "todo"


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[Literal["todo", "doing", "done"]] = None


class TaskResponse(BaseModel):
    id: int
    title: str
    status: str
    user_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedTasks(BaseModel):
    total: int
    page: int
    limit: int
    tasks: list[TaskResponse]