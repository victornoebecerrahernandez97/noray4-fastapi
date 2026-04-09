from pydantic import BaseModel, ConfigDict


class NorayBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
