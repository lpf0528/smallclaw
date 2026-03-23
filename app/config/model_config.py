from pydantic import BaseModel, Field, ConfigDict


class ModelConfig(BaseModel):
    name: str = Field(..., description="Model name")
    # api_key: str = Field(..., description="API key for the model")
    # max_tokens: int = Field(..., description="Maximum tokens of the model")
    # temperature: float = Field(..., description="Temperature of the model")
    model_config = ConfigDict(extra="allow")
    supports_vision: bool = Field(default_factory=lambda: False, description="Whether the model supports vision")
