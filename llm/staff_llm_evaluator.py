import json
import os
import yaml
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent

LABELS = [
    "핵심 역할 수행 가능",
    "일부 역할·일부 기능 담당 가능",
    "참여 불가",
]

RESULT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "project_name": {"type": "string"},
        "source_rfp_file": {"type": "string"},
        "evaluation_summary": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "total_employees": {"type": "integer"},
                "core_role_possible_count": {"type": "integer"},
                "partial_possible_count": {"type": "integer"},
                "not_available_count": {"type": "integer"},
                "overall_comment": {"type": "string"},
            },
            "required": [
                "total_employees",
                "core_role_possible_count",
                "partial_possible_count",
                "not_available_count",
                "overall_comment",
            ],
        },
        "employee_evaluations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "employee_id": {"type": "string"},
                    "name": {"type": "string"},
                    "position": {"type": "string"},
                    "department": {"type": "string"},
                    "label": {"type": "string", "enum": LABELS},
                    "suitable_roles": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "matched_requirements": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "reason": {"type": "string"},
                    "caution": {"type": "string"},
                },
                "required": [
                    "employee_id",
                    "name",
                    "position",
                    "department",
                    "label",
                    "suitable_roles",
                    "matched_requirements",
                    "reason",
                    "caution",
                ],
            },
        },
    },
    "required": [
        "project_name",
        "source_rfp_file",
        "evaluation_summary",
        "employee_evaluations",
    ],
}


def _read_json(path: str | Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: str | Path, data: Dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _build_prompt(
    rfp_context: Dict[str, Any],
    company_staff_pool: Dict[str, Any],
    staff_policy: Dict[str, Any],
    template: str,
) -> str:
    """
    YAML 템플릿에 RFP, 직원, 정책 정보를 주입하여 최종 프롬프트를 생성합니다.
    """
    return template.format(
        rfp_context=json.dumps(rfp_context, ensure_ascii=False, indent=2),
        company_staff_pool=json.dumps(company_staff_pool, ensure_ascii=False, indent=2),
        staff_policy=json.dumps(staff_policy, ensure_ascii=False, indent=2),
    )


def save_markdown(path: str | Path, result: Dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    lines: List[str] = []
    lines.append("# 직원별 프로젝트 참여 가능성 평가 결과\n")
    lines.append(f"- 사업명: {result.get('project_name', '')}")
    lines.append(f"- RFP 파일: {result.get('source_rfp_file', '')}\n")

    summary = result.get("evaluation_summary", {})
    lines.append("## 1. 요약\n")
    lines.append(f"- 전체 직원 수: {summary.get('total_employees', 0)}")
    lines.append(f"- 핵심 역할 수행 가능: {summary.get('core_role_possible_count', 0)}")
    lines.append(f"- 일부 역할·일부 기능 담당 가능: {summary.get('partial_possible_count', 0)}")
    lines.append(f"- 참여 불가: {summary.get('not_available_count', 0)}")
    lines.append(f"- 종합 의견: {summary.get('overall_comment', '')}\n")

    lines.append("## 2. 직원별 평가\n")
    lines.append("| 직원ID | 이름 | 직급 | 라벨 | 적합 역할 | 관련 요구사항 | 주의사항 |")
    lines.append("|---|---|---|---|---|---|---|")

    for item in result.get("employee_evaluations", []):
        roles = ", ".join(item.get("suitable_roles", []))
        reqs = ", ".join(item.get("matched_requirements", []))
        lines.append(
            f"| {item.get('employee_id', '')} "
            f"| {item.get('name', '')} "
            f"| {item.get('position', '')} "
            f"| {item.get('label', '')} "
            f"| {roles} "
            f"| {reqs} "
            f"| {item.get('caution', '')} |"
        )

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def save_excel(path: str | Path, result: Dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    summary = result.get("evaluation_summary", {})
    summary_rows = [
        {"항목": "사업명", "값": result.get("project_name", "")},
        {"항목": "RFP 파일", "값": result.get("source_rfp_file", "")},
        {"항목": "전체 직원 수", "값": summary.get("total_employees", 0)},
        {"항목": "핵심 역할 수행 가능", "값": summary.get("core_role_possible_count", 0)},
        {"항목": "일부 역할·일부 기능 담당 가능", "값": summary.get("partial_possible_count", 0)},
        {"항목": "참여 불가", "값": summary.get("not_available_count", 0)},
        {"항목": "종합 의견", "값": summary.get("overall_comment", "")},
    ]
    df_summary = pd.DataFrame(summary_rows)

    detail_rows: List[Dict[str, Any]] = []
    for item in result.get("employee_evaluations", []):
        detail_rows.append(
            {
                "employee_id": item.get("employee_id", ""),
                "name": item.get("name", ""),
                "position": item.get("position", ""),
                "department": item.get("department", ""),
                "label": item.get("label", ""),
                "suitable_roles": ", ".join(item.get("suitable_roles", [])),
                "matched_requirements": ", ".join(item.get("matched_requirements", [])),
                "reason": item.get("reason", ""),
                "caution": item.get("caution", ""),
            }
        )
    df_detail = pd.DataFrame(detail_rows)

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df_summary.to_excel(writer, index=False, sheet_name="summary")
        df_detail.to_excel(writer, index=False, sheet_name="employee_evaluations")


def evaluate_staff_with_llm(
    rfp_json_path: str | Path,
    staff_pool_json_path: str | Path,
    staff_policy_json_path: str | Path,
    output_json_path: str | Path,
    output_md_path: str | Path,
    output_xlsx_path: str | Path,
    model: str | None = None,
) -> Dict[str, Any]:
    from openai import OpenAI

    # .env 파일 로드 (ROOT_DIR 기준)
    load_dotenv(ROOT_DIR / ".env", override=True)

    rfp_context = _read_json(rfp_json_path)
    staff_pool = _read_json(staff_pool_json_path)
    staff_policy = _read_json(staff_policy_json_path)

    # 프롬프트 템플릿 로드 (YAML 파일에서 시스템 및 사용자 프롬프트 일괄 관리)
    prompt_file = ROOT_DIR / "llm_inputs" / "staff_evaluation_prompt.yaml"
    with open(prompt_file, "r", encoding="utf-8") as f:
        prompt_config = yaml.safe_load(f)

    # YAML 파일의 내용을 우선적으로 사용하며, 코드 내 하드코딩된 프롬프트를 제거하여 충돌 방지
    system_prompt = prompt_config["system_prompt"]
    user_prompt = _build_prompt(
        rfp_context, staff_pool, staff_policy, prompt_config["user_prompt_template"]
    )

    resolved_model = model or os.getenv("OPENAI_MODEL", "gpt-5-mini")
    client = OpenAI()

    response = client.chat.completions.create(
        model=resolved_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "staff_participation_evaluation",
                "strict": True,
                "schema": RESULT_SCHEMA,
            },
        },
    )

    result = json.loads(response.choices[0].message.content)
    _save_json(output_json_path, result)
    save_markdown(output_md_path, result)
    save_excel(output_xlsx_path, result)
    return result
