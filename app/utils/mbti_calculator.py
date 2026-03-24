# -*- coding: utf-8 -*-
"""독서MBTI 점수 계산 유틸리티"""


LEVEL_THRESHOLDS = {
    'beginner': (0, 33.3),
    'intermediate': (33.3, 66.6),
    'advanced': (66.6, 100),
}


def _score_to_level(pct):
    if pct < 33.3:
        return 'beginner'
    elif pct < 66.6:
        return 'intermediate'
    return 'advanced'


def calculate_mbti_scores(questions, responses):
    """
    45개 절대평가 문항(1~5점) + 5개 비교평가 문항(1=A, 2=B)
    → 독해력/사고력/서술력 영역별 백분율 점수와 수준 반환
    """
    resp_map = {r.question_id: r.score for r in responses}

    # 영역별 점수 누적
    domain_scores = {
        'reading': {'sum': 0, 'max': 0},
        'thinking': {'sum': 0, 'max': 0},
        'writing': {'sum': 0, 'max': 0},
    }

    COMPARISON_BONUS = 5  # 비교평가 승리 시 보너스 점수

    for q in questions:
        score = resp_map.get(q.question_id)
        if score is None:
            continue

        if q.question_type == 'absolute':
            domain = q.domain
            if domain in domain_scores:
                domain_scores[domain]['sum'] += score
                domain_scores[domain]['max'] += 5  # 최대 5점

        elif q.question_type == 'comparison':
            # 비교평가: 1=A(domain), 2=B(다른 domain)
            # domain 필드에 'reading_vs_thinking' 같은 형식으로 저장
            if q.domain and '_vs_' in q.domain:
                parts = q.domain.split('_vs_')
                winner_domain = parts[0] if score == 1 else parts[1]
                if winner_domain in domain_scores:
                    domain_scores[winner_domain]['sum'] += COMPARISON_BONUS
                    # 비교평가는 max에 포함하지 않음 (보너스로 처리)

    result = {}
    for domain, data in domain_scores.items():
        if data['max'] > 0:
            base_pct = data['sum'] / data['max'] * 100
        else:
            base_pct = 0
        # 보너스 포함 시 100 초과 가능 → 클램핑
        pct = min(100.0, base_pct)
        result[domain] = {
            'score': round(data['sum'], 2),
            'max': data['max'],
            'pct': round(pct, 1),
            'level': _score_to_level(pct),
        }

    return result


def determine_mbti_type(scores):
    """scores dict → type_code 문자열 (예: 'intermediate_beginner_advanced')"""
    return (f"{scores['reading']['level']}_"
            f"{scores['thinking']['level']}_"
            f"{scores['writing']['level']}")


def validate_responses(questions, form_data):
    """모든 문항에 응답했는지 확인. 누락 question_id 목록 반환"""
    missing = []
    for q in questions:
        if f'q_{q.question_id}' not in form_data:
            missing.append(q.question_id)
    return missing
