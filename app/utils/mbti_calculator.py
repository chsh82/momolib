# -*- coding: utf-8 -*-
"""
독서MBTI 점수 계산 유틸리티

3대 영역(독해력/사고력/서술력) × 3단계 수준(초급/중급/고급) = 9개 세부 능력
각 능력당 5문항, 각 문항 1-5점 → 각 능력 최대 25점
비교 질문(5문항) 보너스 점수 추가
"""


def calculate_mbti_scores(responses):
    """
    응답 dict → 9개 세부 능력 점수 계산

    Args:
        responses (dict): {
            'q1': '3', ..., 'q45': '5',        # 절대평가 1-5점
            'comp1': 'reading:beginner:2,...',  # 비교평가 보너스 명세
        }

    Returns:
        dict: {
            'reading':  {'beginner': 0-25, 'intermediate': 0-25, 'advanced': 0-25},
            'thinking': {'beginner': 0-25, 'intermediate': 0-25, 'advanced': 0-25},
            'writing':  {'beginner': 0-25, 'intermediate': 0-25, 'advanced': 0-25},
        }
    """
    scores = {
        'reading':  {'beginner': 0, 'intermediate': 0, 'advanced': 0},
        'thinking': {'beginner': 0, 'intermediate': 0, 'advanced': 0},
        'writing':  {'beginner': 0, 'intermediate': 0, 'advanced': 0},
    }

    # 문항 번호 → (domain, level) 매핑
    # q1-5: reading beginner, q6-10: reading intermediate, q11-15: reading advanced
    # q16-20: thinking beginner, q21-25: thinking intermediate, q26-30: thinking advanced
    # q31-35: writing beginner, q36-40: writing intermediate, q41-45: writing advanced
    question_mapping = {}
    q_num = 1
    for domain in ['reading', 'thinking', 'writing']:
        for level in ['beginner', 'intermediate', 'advanced']:
            for _ in range(5):
                question_mapping[f'q{q_num}'] = (domain, level)
                q_num += 1

    # 절대평가 (q1-q45)
    for q_key, response in responses.items():
        if q_key.startswith('q') and q_key[1:].isdigit() and q_key in question_mapping:
            try:
                score = int(response)
                if 1 <= score <= 5:
                    domain, level = question_mapping[q_key]
                    scores[domain][level] += score
            except (ValueError, TypeError):
                continue

    # 비교평가 보너스 (comp1-comp5)
    # 형식: "reading:beginner:2,reading:intermediate:3"
    for i in range(1, 6):
        comp_key = f'comp{i}'
        if comp_key in responses and responses[comp_key]:
            parts = responses[comp_key].split(',')
            for part in parts:
                try:
                    domain, level, points = part.strip().split(':')
                    bonus = int(points)
                    if domain in scores and level in scores[domain]:
                        scores[domain][level] += bonus
                except (ValueError, IndexError):
                    continue

    return scores


def determine_mbti_type(scores):
    """
    9개 세부 능력 점수 → MBTI 유형 결정

    Returns:
        tuple: (reading_level, thinking_level, writing_level, type_code)
               예: ('beginner', 'intermediate', 'advanced', 'beginner-intermediate-advanced')
    """
    level_priority = ['advanced', 'intermediate', 'beginner']

    def dominant_level(area_scores):
        max_score = max(area_scores.values())
        for level in level_priority:
            if area_scores[level] == max_score:
                return level
        return 'beginner'

    reading_level = dominant_level(scores['reading'])
    thinking_level = dominant_level(scores['thinking'])
    writing_level = dominant_level(scores['writing'])
    type_code = f"{reading_level}-{thinking_level}-{writing_level}"

    return reading_level, thinking_level, writing_level, type_code


def validate_responses(responses):
    """
    응답 데이터 유효성 검증

    Returns:
        tuple: (is_valid, error_message)
    """
    for i in range(1, 46):
        q_key = f'q{i}'
        if q_key not in responses:
            return False, f'질문 {i}에 응답이 없습니다.'
        try:
            score = int(responses[q_key])
            if not (1 <= score <= 5):
                return False, f'질문 {i}의 응답이 유효하지 않습니다 (1-5 범위).'
        except (ValueError, TypeError):
            return False, f'질문 {i}의 응답 형식이 올바르지 않습니다.'

    for i in range(1, 6):
        comp_key = f'comp{i}'
        if comp_key not in responses or not responses[comp_key]:
            return False, f'비교 질문 {45 + i}에 응답이 없습니다.'

    return True, ''
