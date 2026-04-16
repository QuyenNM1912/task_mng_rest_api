from enum import Enum
from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Literal, Optional


# Auth

class UserRole(str, Enum):
    user = "user"
    admin = "admin"


class UserRoleUpdate(BaseModel):
    role: UserRole


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    role: UserRole = UserRole.user


class UserResponse(BaseModel):
    id: int
    email: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


# Tasks

class TaskStatus(str, Enum):
    todo = "todo"
    doing = "doing"
    done = "done"


class TaskCreate(BaseModel):
    title: str
    status: TaskStatus = TaskStatus.todo


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[TaskStatus] = None


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