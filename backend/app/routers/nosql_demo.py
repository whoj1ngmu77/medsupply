from fastapi import APIRouter, Depends

from app.core.deps import get_current_user
from app.db.mongo import mongo_db
from app.dbms.nosql import (CAP_ANALYSIS, COMPARISON,
                            DOCUMENT_DB_CHARACTERISTICS)
from app.repositories import incident_repo as repo

router = APIRouter(prefix="/dbms/nosql", tags=["DBMS Demonstrations"])


@router.get("/cap", dependencies=[Depends(get_current_user)])
def cap_theorem():
    return CAP_ANALYSIS


@router.get("/characteristics", dependencies=[Depends(get_current_user)])
def characteristics():
    return DOCUMENT_DB_CHARACTERISTICS


@router.get("/comparison", dependencies=[Depends(get_current_user)])
def comparison():
    return COMPARISON


@router.get("/indexes", dependencies=[Depends(get_current_user)])
async def mongo_indexes():
    return {
        "incidents": await mongo_db["incidents"].index_information(),
        "incident_updates": await mongo_db["incident_updates"].index_information(),
        "note": ("MongoDB indexes are B-tree, like PostgreSQL's default. "
                 "The text index on (title, tags) has no direct PostgreSQL "
                 "equivalent without tsvector columns."),
    }
