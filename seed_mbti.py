# -*- coding: utf-8 -*-
"""독서MBTI 테스트 문항 및 유형 시드 스크립트
실행: python seed_mbti.py
"""
from app import create_app
from app.models import db
from app.models.reading_mbti import ReadingMBTITest, ReadingMBTIQuestion, ReadingMBTIType

app = create_app()

# ─── 절대평가 45문항 ───
# domain: reading(독해력), thinking(사고력), writing(서술력)
# level: beginner, intermediate, advanced (각 도메인당 15문항, 수준당 5문항)

ABSOLUTE_QUESTIONS = {
    'reading': {
        'beginner': [
            '나는 글을 읽을 때 중심 내용을 파악할 수 있다.',
            '나는 짧은 글의 주제를 잘 찾는다.',
            '나는 모르는 단어가 나와도 문맥으로 뜻을 유추한다.',
            '나는 글을 읽고 줄거리를 요약할 수 있다.',
            '나는 인물이나 사건의 기본 정보를 파악할 수 있다.',
        ],
        'intermediate': [
            '나는 글쓴이의 의도와 목적을 파악할 수 있다.',
            '나는 글의 구조(서론-본론-결론)를 분석할 수 있다.',
            '나는 글에서 사실과 의견을 구분할 수 있다.',
            '나는 복잡한 문장도 정확하게 이해한다.',
            '나는 글의 숨겨진 의미를 파악할 수 있다.',
        ],
        'advanced': [
            '나는 여러 관점에서 텍스트를 비판적으로 분석할 수 있다.',
            '나는 저자의 편견이나 전제를 발견할 수 있다.',
            '나는 다양한 장르의 글을 능숙하게 이해한다.',
            '나는 행간의 의미와 함축적 표현을 파악한다.',
            '나는 글의 논리적 오류를 찾아낼 수 있다.',
        ],
    },
    'thinking': {
        'beginner': [
            '나는 읽은 내용과 내 경험을 연결할 수 있다.',
            '나는 이야기를 읽고 간단한 질문을 만들 수 있다.',
            '나는 등장인물의 행동 이유를 생각해볼 수 있다.',
            '나는 다음에 어떤 일이 일어날지 예상할 수 있다.',
            '나는 책에서 인상 깊은 부분을 기억한다.',
        ],
        'intermediate': [
            '나는 책의 내용을 현실 상황에 적용해 생각한다.',
            '나는 다른 책이나 지식과 연결하여 이해한다.',
            '나는 글쓴이의 주장을 논리적으로 평가할 수 있다.',
            '나는 같은 주제에 대해 다양한 관점을 생각할 수 있다.',
            '나는 읽은 내용에서 새로운 아이디어를 도출한다.',
        ],
        'advanced': [
            '나는 복잡한 사안에 대해 다각도로 분석할 수 있다.',
            '나는 창의적이고 독창적인 해석을 즐긴다.',
            '나는 읽은 내용을 바탕으로 가설을 세우고 검증한다.',
            '나는 추상적인 개념을 구체적 사례로 설명할 수 있다.',
            '나는 다양한 분야의 지식을 통합적으로 사고한다.',
        ],
    },
    'writing': {
        'beginner': [
            '나는 읽은 책의 내용을 간단히 요약하여 쓸 수 있다.',
            '나는 독서 후 느낀 점을 짧게 쓸 수 있다.',
            '나는 글쓰기에서 맞춤법을 지키려 노력한다.',
            '나는 간단한 문장을 이용해 내 생각을 표현한다.',
            '나는 읽은 내용에 대해 기본적인 서평을 쓸 수 있다.',
        ],
        'intermediate': [
            '나는 주장과 근거를 갖춘 글을 쓸 수 있다.',
            '나는 독서 경험을 논리적 구조로 정리하여 쓴다.',
            '나는 다양한 표현 방식(비유, 예시 등)을 활용한다.',
            '나는 독후 감상문에서 자신만의 시각을 드러낸다.',
            '나는 단락을 나누어 체계적으로 글을 쓴다.',
        ],
        'advanced': [
            '나는 설득력 있는 논술문을 쓸 수 있다.',
            '나는 문체와 어조를 상황에 맞게 조절한다.',
            '나는 복잡한 주제에 대해 깊이 있는 글을 쓴다.',
            '나는 독창적인 관점으로 비평문을 쓴다.',
            '나는 글을 쓴 후 퇴고하여 완성도를 높인다.',
        ],
    },
}

# ─── 비교평가 5문항 ───
COMPARISON_QUESTIONS = [
    {
        'text_a': '책을 읽을 때 세부 내용보다 전체 흐름이 더 중요하다',
        'text_b': '책을 읽을 때 전체 흐름보다 세부 내용이 더 중요하다',
        'domain': 'reading_vs_thinking',
    },
    {
        'text_a': '책을 읽은 후 내 생각을 글로 정리하는 것을 좋아한다',
        'text_b': '책을 읽은 후 다른 사람과 토론하는 것을 좋아한다',
        'domain': 'writing_vs_thinking',
    },
    {
        'text_a': '새로운 어휘와 표현을 배우는 것이 독서의 가장 큰 즐거움이다',
        'text_b': '새로운 관점과 아이디어를 얻는 것이 독서의 가장 큰 즐거움이다',
        'domain': 'reading_vs_thinking',
    },
    {
        'text_a': '글을 쓸 때 논리와 구조를 먼저 잡는다',
        'text_b': '글을 쓸 때 감정과 직관을 먼저 따른다',
        'domain': 'writing_vs_thinking',
    },
    {
        'text_a': '독서 후 내용을 정확하게 기억하는 것이 더 중요하다',
        'text_b': '독서 후 자신만의 해석을 갖는 것이 더 중요하다',
        'domain': 'reading_vs_thinking',
    },
]

# ─── 27가지 유형 ───
LEVELS = ['beginner', 'intermediate', 'advanced']
LEVEL_NAMES = {'beginner': '초급', 'intermediate': '중급', 'advanced': '고급'}

EMOJIS = {
    'beginner_beginner_beginner': '🌱',
    'beginner_beginner_intermediate': '🌿',
    'beginner_beginner_advanced': '✏️',
    'beginner_intermediate_beginner': '🔍',
    'beginner_intermediate_intermediate': '🧩',
    'beginner_intermediate_advanced': '📖',
    'beginner_advanced_beginner': '💡',
    'beginner_advanced_intermediate': '🌟',
    'beginner_advanced_advanced': '🎯',
    'intermediate_beginner_beginner': '📚',
    'intermediate_beginner_intermediate': '🗒️',
    'intermediate_beginner_advanced': '✍️',
    'intermediate_intermediate_beginner': '🔎',
    'intermediate_intermediate_intermediate': '⚖️',
    'intermediate_intermediate_advanced': '📝',
    'intermediate_advanced_beginner': '🧠',
    'intermediate_advanced_intermediate': '💫',
    'intermediate_advanced_advanced': '🏆',
    'advanced_beginner_beginner': '📜',
    'advanced_beginner_intermediate': '🖊️',
    'advanced_beginner_advanced': '🎓',
    'advanced_intermediate_beginner': '🔭',
    'advanced_intermediate_intermediate': '⭐',
    'advanced_intermediate_advanced': '🌈',
    'advanced_advanced_beginner': '🧬',
    'advanced_advanced_intermediate': '🌠',
    'advanced_advanced_advanced': '👑',
}

TYPE_NAMES = {
    'beginner': '탐색하는', 'intermediate': '성장하는', 'advanced': '통달한'
}

DOMAIN_NAMES = {
    'reading': '독서가', 'thinking': '사색가', 'writing': '작가'
}


def generate_type_name(r, t, w):
    r_adj = TYPE_NAMES[r]
    dominant = max([(r, 'reading'), (t, 'thinking'), (w, 'writing')],
                   key=lambda x: LEVELS.index(x[0]))
    return f"{r_adj} {DOMAIN_NAMES[dominant[1]]}"


def seed_mbti():
    with app.app_context():
        db.create_all()

        # 기존 데이터 초기화
        ReadingMBTIType.query.delete()
        ReadingMBTIQuestion.query.delete()
        ReadingMBTITest.query.delete()
        db.session.commit()

        # 테스트 생성
        test = ReadingMBTITest(
            name='독서MBTI 테스트',
            description='독해력·사고력·서술력 3개 영역, 50문항으로 나의 독서 유형을 파악합니다.',
            is_active=True,
        )
        db.session.add(test)
        db.session.flush()

        # 절대평가 문항 추가
        order = 0
        for domain in ['reading', 'thinking', 'writing']:
            for level in ['beginner', 'intermediate', 'advanced']:
                for q_text in ABSOLUTE_QUESTIONS[domain][level]:
                    q = ReadingMBTIQuestion(
                        test_id=test.test_id,
                        question_type='absolute',
                        domain=domain,
                        level=level,
                        question_text=q_text,
                        order_num=order,
                    )
                    db.session.add(q)
                    order += 1

        # 비교평가 문항 추가
        for cq in COMPARISON_QUESTIONS:
            q = ReadingMBTIQuestion(
                test_id=test.test_id,
                question_type='comparison',
                domain=cq['domain'],
                question_text=cq['text_a'],
                question_text_b=cq['text_b'],
                order_num=order,
            )
            db.session.add(q)
            order += 1

        # 27가지 유형 추가
        for r in LEVELS:
            for t in LEVELS:
                for w in LEVELS:
                    code = f'{r}_{t}_{w}'
                    type_name = generate_type_name(r, t, w)
                    rn, tn, wn = LEVEL_NAMES[r], LEVEL_NAMES[t], LEVEL_NAMES[w]
                    description = (
                        f"독해력 {rn}, 사고력 {tn}, 서술력 {wn}인 독서 유형입니다. "
                        f"책을 읽고 이해하는 능력과 생각을 정리하고 표현하는 역량을 고루 갖추고 있습니다."
                    )
                    strengths, weaknesses, recommendation = _get_swot(r, t, w)
                    mbti_type = ReadingMBTIType(
                        type_code=code,
                        type_name=type_name,
                        reading_level=r,
                        thinking_level=t,
                        writing_level=w,
                        description=description,
                        strengths=strengths,
                        weaknesses=weaknesses,
                        recommendation=recommendation,
                        emoji=EMOJIS.get(code, '📚'),
                    )
                    db.session.add(mbti_type)

        db.session.commit()
        print(f"[OK] MBTI seed done: test=1, questions={order}, types=27")


def _get_swot(r, t, w):
    lvl = {'beginner': 0, 'intermediate': 1, 'advanced': 2}
    r_i, t_i, w_i = lvl[r], lvl[t], lvl[w]
    total = r_i + t_i + w_i

    if total <= 1:
        strengths = "꾸준히 독서하는 기초 습관을 갖추고 있습니다."
        weaknesses = "독서 기초 역량을 전반적으로 강화할 필요가 있습니다."
        recommendation = "쉬운 그림책이나 짧은 이야기책부터 시작하여 독서 습관을 형성하세요."
    elif total <= 3:
        strengths = f"{'독해력' if r_i == max(r_i, t_i, w_i) else '사고력' if t_i == max(r_i, t_i, w_i) else '서술력'}이 강점입니다."
        weaknesses = "일부 영역에서 추가적인 훈련이 필요합니다."
        recommendation = "강점 영역을 유지하면서 약한 영역을 집중적으로 발전시키세요."
    elif total <= 5:
        strengths = "균형 잡힌 독서 역량을 갖추고 있으며 지속적으로 성장하고 있습니다."
        weaknesses = "고급 수준의 비판적 사고력을 더 키울 수 있습니다."
        recommendation = "다양한 장르와 주제의 책을 통해 독서 범위를 넓히고 심층적 분석을 연습하세요."
    else:
        strengths = "세 가지 독서 역량 모두 높은 수준으로, 탁월한 독서 능력을 보유하고 있습니다."
        weaknesses = "현재 수준을 유지하고 더욱 심화된 작품에 도전하는 것이 과제입니다."
        recommendation = "고전 문학, 학술 논문 등 난이도 높은 텍스트로 도전의 범위를 확장하세요."

    return strengths, weaknesses, recommendation


if __name__ == '__main__':
    seed_mbti()
