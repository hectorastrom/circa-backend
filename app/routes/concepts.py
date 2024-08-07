from app.models.models import ConceptModel, UpdateConceptModel
from app.routes.common_imports import *
from app.helpers.similarity import calculate_normalized_embeddings, tensor_to_list
from typing import List


router = APIRouter()


async def find_concept_by_id(db: DbDep, id: str):
    """
    Finds a concept by id and returns it.

    Raises exceptions for invalid ID format and non-existant concepts.
    """
    try:
        object_id = ObjectId(id)
    except errors.InvalidId:
        raise HTTPException(status_code=400, detail=f"Invalid concept ID format: {id}")

    concept = await db.concepts.find_one({"_id": object_id})
    if not concept:
        raise HTTPException(status_code=404, detail=f"Concept not found with id={id}")
    return concept


@router.post(
    "/concepts",
    response_description="Insert new concept",
    status_code=status.HTTP_201_CREATED,
    # can return either ConceptModel(**created_concept) or created_concept, as
    # specifying response_model as ConceptModel lets FastAPI know what to expect
    response_model=ConceptModel,
    response_model_by_alias=False,
)
async def add_concept(
    db : DbDep, concept: ConceptModel = Body(...)
):
    """
    Insert a concept record (id ignored) and return it.
    A unique `id` will be created.
    """
    # returns InsertOneResult, which has inserted_id attribute
    # exclude "id" so MongoDB can create its own
    new_concept = await db.concepts.insert_one(
        concept.model_dump(by_alias=True, exclude=["id"])
    )
    created_concept = await db.concepts.find_one({"_id": new_concept.inserted_id})
    return created_concept


@router.get(
    "/concepts",
    response_description="Fetch all concepts",
    response_model=List[ConceptModel],
    response_model_by_alias=False,
    status_code=status.HTTP_200_OK,
)
async def get_concepts(db: DbDep):
    """
    Fetch all concepts in the database

    Results limited to 1000 records
    """
    concepts_cursor = db.concepts.find()
    concepts = await concepts_cursor.to_list(length=1000)
    output = [ConceptModel(**concept) for concept in concepts]
    return output


@router.get(
    "/concepts/{id}",
    response_description="Fetch a concept by id",
    response_model=ConceptModel,
    response_model_by_alias=False,
    status_code=status.HTTP_200_OK,
)
async def get_concept_by_id(db: DbDep, id: str):
    """
    Find one concept record by id
    """
    try:
        object_id = ObjectId(id)
    except errors.InvalidId:
        raise HTTPException(status_code=400, detail=f"Invalid user ID format: {id}")

    concept = await db.concepts.find_one({"_id": object_id})
    if not concept:
        raise HTTPException(404, detail=f"Concept not found {id=}")
    return concept


@router.put(
    "/concepts/{id}",
    response_description="Update a concept",
    response_model=ConceptModel,
    response_model_by_alias=False,
    status_code=status.HTTP_200_OK,
)
async def update_concept(
    db: DbDep,  # Dependency
    id: str,  # Path parameter
    update_data: UpdateConceptModel = Body(...),  # Request body
):
    """
    Updates an existing concept on name or usage, or returns the existing
    concept without any update_data provided.

    The normalized_embedding, if the concept is updated, is automatically
    recalculated.
    """
    concept = await find_concept_by_id(db, id)
    # if we got this far, the concept exists

    update_data_dict = {
        k: v for k, v in update_data.model_dump(by_alias=True).items() if v is not None
    }

    # Recalculate the normalized_embedding if name or usage is updated
    if "name" in update_data_dict or "usage" in update_data_dict:
        embed_string = f"{update_data_dict.get('name', concept['name'])}: {update_data_dict.get('usage', concept['usage'])}"
        update_data_dict["normalized_embedding"] = tensor_to_list(
            calculate_normalized_embeddings(embed_string)
        )

    if update_data_dict:
        await db.concepts.update_one(
            {"_id": concept["_id"]},
            {"$set": update_data_dict},
        )
        updated_concept = await db.concepts.find_one({"_id": concept["_id"]})
        return updated_concept

    return concept


@router.delete(
    "/concepts/{id}",
    response_description="Delete a concept by id",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_concept(db: DbDep, id: str):
    """
    Delete a concept by id
    """
    delete_result = await db.concepts.delete_one({"_id": ObjectId(id)})
    if delete_result.deleted_count == 1:
        return JSONResponse(
            content={"message": f"Concept with {id=} deleted."},
            status_code=status.HTTP_200_OK,
        )
    raise HTTPException(status_code=404, detail=f"Concept with {id=} not found.")
