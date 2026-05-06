"""
테스트 케이스 기반 정확도(Accuracy) 측정 스크립트.

data/test_cases/ 디렉토리 구조:
  test_cases/
    interview/
      yes/   <- 적합한 착장 이미지
      no/    <- 부적합한 착장 이미지
    funeral/
      yes/
      no/
    presentation/
      yes/
      no/
"""

import base64
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent import classify, VALID_SITUATIONS

TEST_DIR = os.path.join(os.path.dirname(__file__), "../data/test_cases")


def load_image_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def evaluate_situation(situation: str) -> dict:
    results = {"TP": 0, "TN": 0, "FP": 0, "FN": 0, "errors": []}

    for label in ("yes", "no"):
        expected = label.upper()
        dir_path = os.path.join(TEST_DIR, situation, label)
        if not os.path.exists(dir_path):
            continue

        for fname in os.listdir(dir_path):
            if not fname.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            fpath = os.path.join(dir_path, fname)
            try:
                img_b64 = load_image_base64(fpath)
                pred = classify(img_b64, situation)
                predicted = pred["result"]
            except Exception as e:
                results["errors"].append({"file": fname, "error": str(e)})
                continue

            if expected == "YES" and predicted == "YES":
                results["TP"] += 1
            elif expected == "NO" and predicted == "NO":
                results["TN"] += 1
            elif expected == "NO" and predicted == "YES":
                results["FP"] += 1
            elif expected == "YES" and predicted == "NO":
                results["FN"] += 1

    total = results["TP"] + results["TN"] + results["FP"] + results["FN"]
    accuracy = (results["TP"] + results["TN"]) / total if total > 0 else 0.0
    return {"situation": situation, "accuracy": round(accuracy, 4), "total": total, **results}


def main():
    all_results = []
    for situation in VALID_SITUATIONS:
        result = evaluate_situation(situation)
        all_results.append(result)
        print(f"[{situation}] accuracy={result['accuracy']} ({result['TP']+result['TN']}/{result['total']})")

    print("\n=== Summary ===")
    print(json.dumps(all_results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
