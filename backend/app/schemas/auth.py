from pydantic import BaseModel, EmailStr, Field

# The UserCreate, UserRead, and Token classes are Pydantic models that define the structure of data used for user creation, user retrieval, and authentication token representation in the application. 

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=160)


class UserRead(BaseModel):
    id: int
    email: EmailStr
    full_name: str | None
    is_active: bool

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
