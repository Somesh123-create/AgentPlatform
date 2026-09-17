def test_catalog_module_imports():
    from app.models.llm import LLMModel, LLMProvider
    assert LLMModel.__tablename__ == "llm_models"
    assert LLMProvider.__tablename__ == "llm_providers"
