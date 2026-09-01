from __future__ import annotations

import json

from ml_augmented_training import train_objectif1, train_objectif2
from mlops_registry import get_mlops_status


def main() -> None:
    result_obj1 = train_objectif1(save_model=True)
    result_obj2 = train_objectif2(save_model=True)
    status = get_mlops_status()

    payload = {
        "pipeline_status": "completed",
        "objectif1": {
            "best_model_name": result_obj1.best_model_name,
            "metrics": result_obj1.comparison.iloc[0].to_dict() if not result_obj1.comparison.empty else {},
            "mlflow_tracking": result_obj1.mlflow_tracking,
        },
        "objectif2": {
            "best_model_name": result_obj2.best_model_name,
            "metrics": result_obj2.comparison.iloc[0].to_dict() if not result_obj2.comparison.empty else {},
            "mlflow_tracking": result_obj2.mlflow_tracking,
        },
        "mlops_status": status,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
