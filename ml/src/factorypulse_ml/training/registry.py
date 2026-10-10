"""MLflow model registry operations."""
import logging
import mlflow
from mlflow.tracking import MlflowClient

logger = logging.getLogger(__name__)


def register_model(run_id: str, model_name: str) -> str:
    """Register a model run to the MLflow registry."""
    try:
        model_uri = f"runs:/{run_id}/model"
        result = mlflow.register_model(model_uri, model_name)
        logger.info(f"Registered model '{model_name}' version {result.version}")
        
        # Optionally transition to staging automatically
        client = MlflowClient()
        client.transition_model_version_stage(
            name=model_name,
            version=result.version,
            stage="Staging"
        )
        logger.info(f"Transitioned '{model_name}' version {result.version} to Staging")
        return result.version
    except Exception as e:
        logger.error(f"Failed to register model: {e}")
        return ""


def get_latest_model_version(model_name: str, stage: str = "Production") -> str:
    """Get the latest version of a model in a specific stage."""
    try:
        client = MlflowClient()
        versions = client.get_latest_versions(model_name, stages=[stage])
        if versions:
            return versions[0].version
        return ""
    except Exception as e:
        logger.error(f"Failed to get model version: {e}")
        return ""
