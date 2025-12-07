from pydantic import BaseModel, Field

class Structure(BaseModel):
    tldr: str = Field(description="describe the main task of this paper")
    motivation: str = Field(description="describe the motivation in this paper")
    method: str = Field(description="method of this paper")
    result: str = Field(description="result of this paper")
    conclusion: str = Field(description="conclusion of this paper")
