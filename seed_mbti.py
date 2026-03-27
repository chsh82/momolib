#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
독서MBTI 초기 데이터 삽입 스크립트
실행: python seed_mbti.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db
from app.models.reading_mbti import (
    ReadingMBTITest, ReadingMBTIQuestion, ReadingMBTIType,
    ReadingMBTIResponse, ReadingMBTIResult
)

app = create_app()

with app.app_context():
    print("=" * 60)
    print("독서MBTI 초기 데이터 삽입")
    print("=" * 60)

    existing = ReadingMBTITest.query.first()
    if existing:
        ans = input("기존 테스트 데이터를 삭제하고 새로 삽입하시겠습니까? (y/N): ")
        if ans.lower() != 'y':
            print("취소됨.")
            sys.exit(0)
        ReadingMBTIResult.query.delete()
        ReadingMBTIResponse.query.delete()
        ReadingMBTIQuestion.query.delete()
        ReadingMBTIType.query.delete()
        ReadingMBTITest.query.delete()
        db.session.commit()
        print("기존 데이터 삭제 완료")

    # ── 1. 테스트 생성 ──────────────────────────────────────────
    test = ReadingMBTITest(
        name='MOMO 논술 MBTI 역량 진단',
        description='독해력, 사고력, 서술력을 9가지 세부 능력으로 분석하여 학습자 수준을 진단합니다',
        is_active=True,
    )
    db.session.add(test)
    db.session.commit()
    print(f"테스트 생성: {test.name} (ID: {test.test_id})")

    # ── 2. 45개 절대평가 질문 ────────────────────────────────────
    questions_data = [
        # 독해력 초급 (기본 문해력)
        {'domain': 'reading', 'level': 'beginner', 'text': '글을 읽다가 모르는 단어가 나오면 그 자리에서 사전이나 검색을 통해 찾아본다'},
        {'domain': 'reading', 'level': 'beginner', 'text': '문장에서 "그러나", "따라서" 같은 접속어를 보면 앞뒤 문맥을 연결해서 의미를 파악한다'},
        {'domain': 'reading', 'level': 'beginner', 'text': '"민주주의"와 "민주정치"처럼 비슷한 단어의 차이를 구분하려고 노력한다'},
        {'domain': 'reading', 'level': 'beginner', 'text': '같은 단어라도 문맥에 따라 의미가 달라진다는 것을 알고 주의해서 읽는다'},
        {'domain': 'reading', 'level': 'beginner', 'text': '새로운 단어를 배우면 예문을 찾아보거나 직접 문장을 만들어본다'},
        # 독해력 중급 (구조적 독해)
        {'domain': 'reading', 'level': 'intermediate', 'text': '중요한 지문은 시험 전이나 과제할 때 최소 2번 이상 다시 읽는다'},
        {'domain': 'reading', 'level': 'intermediate', 'text': '같은 글을 다시 읽으면 "아, 이런 의미였구나" 하고 새롭게 이해되는 부분이 있다'},
        {'domain': 'reading', 'level': 'intermediate', 'text': '글을 읽을 때 중요한 숫자, 날짜, 고유명사 등을 놓치지 않으려고 신경 쓴다'},
        {'domain': 'reading', 'level': 'intermediate', 'text': '저자가 직접 말하지 않았지만 암시하는 내용이 무엇인지 생각하며 읽는다'},
        {'domain': 'reading', 'level': 'intermediate', 'text': '처음 읽을 때보다 두 번째 읽을 때 내용이 훨씬 더 잘 이해된다'},
        # 독해력 고급 (비판적 독해)
        {'domain': 'reading', 'level': 'advanced', 'text': '글을 읽을 때 "이 글의 구조는 원인→결과, 문제제기→해결방안" 같은 틀을 파악한다'},
        {'domain': 'reading', 'level': 'advanced', 'text': '글에서 저자의 주장과 주장을 뒷받침하는 근거를 구분하며 읽는다'},
        {'domain': 'reading', 'level': 'advanced', 'text': '글을 읽다가 "이 근거로는 주장이 약한데"라고 의문을 가질 때가 있다'},
        {'domain': 'reading', 'level': 'advanced', 'text': '글을 읽고 나서 "이 주장에 동의하는가"를 스스로 판단해본다'},
        {'domain': 'reading', 'level': 'advanced', 'text': '글을 읽으면 "이 내용을 우리 학교/우리 동네에 적용하면"처럼 확장해서 생각한다'},

        # 사고력 초급 (내용 전달)
        {'domain': 'thinking', 'level': 'beginner', 'text': '토론할 때 책이나 자료 내용을 정확히 인용하며 말한다'},
        {'domain': 'thinking', 'level': 'beginner', 'text': '내 생각을 말할 때 "제 의견은 크게 3가지입니다"처럼 구조화해서 말한다'},
        {'domain': 'thinking', 'level': 'beginner', 'text': '토론 중 내 주장을 할 때 반드시 책이나 자료의 내용을 근거로 제시한다'},
        {'domain': 'thinking', 'level': 'beginner', 'text': '친구가 발표할 때 끝까지 듣고 "그 부분은 ~라는 뜻인가요"처럼 질문한다'},
        {'domain': 'thinking', 'level': 'beginner', 'text': '토론할 때 정해진 순서를 지키고 다른 사람 말을 끊지 않으려고 노력한다'},
        # 사고력 중급 (논리적 표현)
        {'domain': 'thinking', 'level': 'intermediate', 'text': '토론 주제가 나오면 뉴스에서 본 사건이나 사례와 연결해서 생각한다'},
        {'domain': 'thinking', 'level': 'intermediate', 'text': '찬성 입장과 반대 입장을 모두 생각해보며 여러 시각으로 주제를 바라본다'},
        {'domain': 'thinking', 'level': 'intermediate', 'text': '내 주장을 설명할 때 "예를 들어"라며 실제 있었던 일이나 경험을 이야기한다'},
        {'domain': 'thinking', 'level': 'intermediate', 'text': '한 주제를 토론하다가 "이건 다른 문제와도 연결되는데"라며 주제를 확장한다'},
        {'domain': 'thinking', 'level': 'intermediate', 'text': '주장을 말할 때 논리적 설명과 함께 감정적 공감도 함께 활용한다'},
        # 사고력 고급 (창의적 확장)
        {'domain': 'thinking', 'level': 'advanced', 'text': '토론이 막히면 "이런 관점에서는 어떨까요"라며 새로운 질문을 던진다'},
        {'domain': 'thinking', 'level': 'advanced', 'text': '토론 중 "지금까지 나온 의견을 정리하면~"이라며 흐름을 요약한다'},
        {'domain': 'thinking', 'level': 'advanced', 'text': '여러 친구들의 의견을 듣고 "A와 B의 공통점은 ~이네요"라고 연결한다'},
        {'domain': 'thinking', 'level': 'advanced', 'text': '토론하다가 "우리가 놓친 부분이 있는데"라고 새로운 쟁점을 제시한다'},
        {'domain': 'thinking', 'level': 'advanced', 'text': '조별 토론에서 각 사람에게 역할을 배분하고 토론을 이끈다'},

        # 서술력 초급 (간결한 요약)
        {'domain': 'writing', 'level': 'beginner', 'text': '긴 글을 읽고 나서 핵심 내용 3~5가지를 뽑아낼 수 있다'},
        {'domain': 'writing', 'level': 'beginner', 'text': '요약할 때 "이건 예시니까 빼고, 이건 핵심이니까 넣자"라고 판단한다'},
        {'domain': 'writing', 'level': 'beginner', 'text': '요약문을 쓸 때 짧고 간결하게, 핵심만 담으려고 노력한다'},
        {'domain': 'writing', 'level': 'beginner', 'text': '요약할 때 "내 생각에는~"이 아니라 글쓴이의 내용만 객관적으로 쓴다'},
        {'domain': 'writing', 'level': 'beginner', 'text': '내가 쓴 요약문만 읽어도 원문의 핵심을 이해할 수 있도록 작성한다'},
        # 서술력 중급 (체계적 구성)
        {'domain': 'writing', 'level': 'intermediate', 'text': '글을 쓰기 전에 "이 글의 주제는 정확히 무엇인가"를 먼저 정한다'},
        {'domain': 'writing', 'level': 'intermediate', 'text': '글을 쓸 때 서론-본론-결론 순서로 구조를 잡고 쓴다'},
        {'domain': 'writing', 'level': 'intermediate', 'text': '주장을 쓴 다음 "왜냐하면~"으로 근거를 연결하며 논리적으로 쓴다'},
        {'domain': 'writing', 'level': 'intermediate', 'text': '어려운 개념을 설명할 때 "쉽게 말하면", "예를 들어"를 사용해서 풀어쓴다'},
        {'domain': 'writing', 'level': 'intermediate', 'text': '결론 부분에서 서론의 질문에 대한 명확한 답을 제시한다'},
        # 서술력 고급 (창의적 재구성)
        {'domain': 'writing', 'level': 'advanced', 'text': '친구 글을 읽으면 "이 부분은 순서를 바꾸면 더 좋겠다"라는 생각이 든다'},
        {'domain': 'writing', 'level': 'advanced', 'text': '내 글을 다시 읽으면 문장 연결이 어색한 부분을 발견하고 고칠 수 있다'},
        {'domain': 'writing', 'level': 'advanced', 'text': '같은 주제로 글을 쓰더라도 전혀 다른 방식으로 표현해보려고 시도한다'},
        {'domain': 'writing', 'level': 'advanced', 'text': '글을 쓸 때 반대 입장의 반박을 미리 생각하고 대응책을 포함한다'},
        {'domain': 'writing', 'level': 'advanced', 'text': '내 글에 다른 사람의 시각이나 비유를 섞어서 더 풍부하게 만든다'},
    ]

    for i, q in enumerate(questions_data, 1):
        db.session.add(ReadingMBTIQuestion(
            test_id=test.test_id,
            question_type='absolute',
            domain=q['domain'],
            level=q['level'],
            question_text=q['text'],
            order_num=i,
        ))
    db.session.commit()
    print("절대평가 질문 45개 삽입 완료")

    # ── 3. 5개 비교 질문 ────────────────────────────────────────
    comparison_data = [
        {
            'text': '나에게 가장 잘 맞는 학습 방법은?',
            'options': [
                {'t': '어려운 개념을 반복해서 읽고 외워서 완벽하게 이해한다', 'v': 'reading:beginner:2,reading:intermediate:3'},
                {'t': '책의 전체 구조와 흐름을 파악한 후 세부 내용을 공부한다', 'v': 'reading:intermediate:2,reading:advanced:3'},
                {'t': '내용을 비판적으로 검토하고 다른 자료와 비교하며 공부한다', 'v': 'reading:advanced:3,thinking:advanced:2'},
            ]
        },
        {
            'text': '토론할 때 나의 강점은?',
            'options': [
                {'t': '자료를 정확히 인용하고 체계적으로 말할 수 있다', 'v': 'thinking:beginner:3,thinking:intermediate:2'},
                {'t': '여러 관점을 제시하고 논리적으로 반박할 수 있다', 'v': 'thinking:intermediate:3,thinking:advanced:2'},
                {'t': '토론을 이끌고 의견을 종합해서 새로운 해결책을 제시한다', 'v': 'thinking:advanced:3,writing:advanced:2'},
            ]
        },
        {
            'text': '글을 쓸 때 나의 스타일은?',
            'options': [
                {'t': '핵심 내용을 간결하고 명확하게 정리해서 쓴다', 'v': 'writing:beginner:3,writing:intermediate:2'},
                {'t': '논리적 구조를 잡고 체계적으로 서술한다', 'v': 'writing:intermediate:3,writing:advanced:2'},
                {'t': '기존 내용을 비판적으로 재구성하고 창의적으로 표현한다', 'v': 'writing:advanced:3,reading:advanced:2'},
            ]
        },
        {
            'text': '새로운 주제를 학습할 때 나의 방식은?',
            'options': [
                {'t': '기본 개념과 용어를 먼저 정확히 이해한다', 'v': 'reading:beginner:2,writing:beginner:2,thinking:beginner:1'},
                {'t': '전체 맥락을 파악하고 다른 사람에게 설명해본다', 'v': 'reading:intermediate:2,thinking:intermediate:2,writing:intermediate:1'},
                {'t': '비판적으로 분석하고 나만의 관점으로 재해석한다', 'v': 'reading:advanced:2,thinking:advanced:2,writing:advanced:1'},
            ]
        },
        {
            'text': '과제나 시험을 준비할 때 나의 강점은?',
            'options': [
                {'t': '중요한 내용을 빠짐없이 정리하고 암기한다', 'v': 'reading:beginner:1,reading:intermediate:2,writing:beginner:2'},
                {'t': '논리적으로 구조화하고 예시를 들어 설명한다', 'v': 'reading:intermediate:1,thinking:intermediate:2,writing:intermediate:2'},
                {'t': '창의적으로 재구성하고 심화 내용까지 확장한다', 'v': 'reading:advanced:1,thinking:advanced:2,writing:advanced:2'},
            ]
        },
    ]

    for i, cq in enumerate(comparison_data, 1):
        db.session.add(ReadingMBTIQuestion(
            test_id=test.test_id,
            question_type='comparison',
            question_text=cq['text'],
            options=cq['options'],
            order_num=45 + i,
        ))
    db.session.commit()
    print("비교 질문 5개 삽입 완료")

    # ── 4. 27가지 유형 데이터 ────────────────────────────────────
    levels_meta = {
        'beginner':     {'name': '초급'},
        'intermediate': {'name': '중급'},
        'advanced':     {'name': '고급'},
    }
    reading_styles = {
        'beginner':     "기본 어휘와 문장 구조를 파악하는 수준입니다. 모르는 단어를 찾아보고 문맥을 이해하려 노력합니다.",
        'intermediate': "문단의 구조와 주제를 파악할 수 있으며, 반복 독해를 통해 심층적으로 이해합니다.",
        'advanced':     "글의 논리 구조를 분석하고 저자의 의도를 비판적으로 평가할 수 있습니다.",
    }
    speaking_styles = {
        'beginner':     "이해한 내용을 전달하고 자료를 근거로 의견을 표현할 수 있습니다.",
        'intermediate': "여러 관점을 제시하고 논리적으로 근거를 제시할 수 있습니다. 주제를 확장하는 능력이 있습니다.",
        'advanced':     "토론을 이끌고 의견을 종합하며 새로운 관점을 제시할 수 있습니다.",
    }
    writing_styles = {
        'beginner':     "핵심 내용을 간결하게 요약하고 정리할 수 있습니다.",
        'intermediate': "논리적 구조를 갖추고 체계적으로 서술할 수 있습니다.",
        'advanced':     "내용을 비판적으로 재구성하고 창의적으로 표현할 수 있습니다.",
    }

    for rl in ['beginner', 'intermediate', 'advanced']:
        for tl in ['beginner', 'intermediate', 'advanced']:
            for wl in ['beginner', 'intermediate', 'advanced']:
                rn = levels_meta[rl]['name']
                tn = levels_meta[tl]['name']
                wn = levels_meta[wl]['name']
                type_code = f"{rl}-{tl}-{wl}"

                if rl == tl == wl:
                    names = {'beginner': ("기초 학습자", "모든 영역에서 기본기를 다지는 단계"),
                             'intermediate': ("균형 발전형", "모든 영역이 고르게 발달한 학습자"),
                             'advanced': ("통합 마스터", "모든 영역에서 고급 역량을 갖춘 학습자")}
                    type_name, combo_desc = names[rl]
                else:
                    max_lv = max([rl, tl, wl], key=lambda x: ['beginner', 'intermediate', 'advanced'].index(x))
                    if max_lv == 'advanced':
                        if rl == 'advanced':
                            type_name, combo_desc = f"{rn}독해 전문가", "독해력이 뛰어난 분석적 학습자"
                        elif tl == 'advanced':
                            type_name, combo_desc = f"{tn}토론 리더", "사고력과 토론 능력이 뛰어난 학습자"
                        else:
                            type_name, combo_desc = f"{wn}작문 전문가", "서술력이 뛰어난 표현적 학습자"
                    elif max_lv == 'intermediate':
                        if rl == 'intermediate':
                            type_name, combo_desc = f"{rn}독해 발전형", "독해력이 성장 중인 학습자"
                        elif tl == 'intermediate':
                            type_name, combo_desc = f"{tn}토론 성장형", "사고력이 발달 중인 학습자"
                        else:
                            type_name, combo_desc = f"{wn}작문 성장형", "서술력이 향상 중인 학습자"
                    else:
                        type_name, combo_desc = "잠재력 발굴형", "기초를 다지며 성장하는 학습자"

                full_desc = f"독해력 {rn}, 사고력 {tn}, 서술력 {wn} 수준의 학습자입니다. "
                if rl == tl == wl:
                    extra = {'beginner': "꾸준한 학습으로 전 영역의 향상을 기대할 수 있습니다.",
                             'intermediate': "심화 학습으로 한 단계 더 도약할 준비가 되어 있습니다.",
                             'advanced': "전문적인 학습과 실전 경험으로 더욱 발전할 수 있습니다."}
                    full_desc += extra[rl]
                else:
                    strong = [x for x, lv in [('독해력', rl), ('사고력', tl), ('서술력', wl)] if lv == 'advanced']
                    weak = [x for x, lv in [('독해력', rl), ('사고력', tl), ('서술력', wl)] if lv == 'beginner']
                    if strong:
                        full_desc += f"{', '.join(strong)}이 뛰어나며, "
                    if weak:
                        full_desc += f"{', '.join(weak)}을 집중적으로 보완하면 균형잡힌 학습자로 성장할 수 있습니다."
                    else:
                        full_desc += "각 영역의 수준 차이를 고려한 맞춤형 학습이 효과적입니다."

                strengths, weaknesses, tips = [], [], []
                if rl == 'advanced':
                    strengths.append("복잡한 텍스트를 빠르게 이해하고 분석할 수 있음")
                    tips.append("심화 독서를 통해 배경지식을 넓히세요")
                elif rl == 'intermediate':
                    strengths.append("체계적으로 읽고 주요 내용을 파악할 수 있음")
                    tips.append("비판적 독해 연습으로 분석력을 키우세요")
                else:
                    weaknesses.append("긴 글이나 복잡한 내용을 이해하는 데 시간이 필요함")
                    tips.append("매일 꾸준히 읽고 모르는 단어를 정리하세요")

                if tl == 'advanced':
                    strengths.append("논리적으로 사고하고 창의적으로 표현할 수 있음")
                    tips.append("디베이트나 발표 기회를 적극 활용하세요")
                elif tl == 'intermediate':
                    strengths.append("여러 관점을 이해하고 논리적으로 설명할 수 있음")
                    tips.append("토론 활동에 참여하며 다양한 관점을 연습하세요")
                else:
                    weaknesses.append("즉흥적인 발표나 토론에서 어려움을 느낌")
                    tips.append("생각을 미리 정리하고 발표 연습을 자주 하세요")

                if wl == 'advanced':
                    strengths.append("논리적이고 창의적인 글쓰기가 가능함")
                    tips.append("다양한 장르의 글쓰기에 도전하세요")
                elif wl == 'intermediate':
                    strengths.append("체계적으로 구조화하여 글을 쓸 수 있음")
                    tips.append("글쓰기 후 퇴고하는 습관을 들이세요")
                else:
                    weaknesses.append("긴 글을 쓰거나 논리적으로 전개하는 것이 어려움")
                    tips.append("짧은 글부터 시작해 점진적으로 분량을 늘려가세요")

                if rl == tl == wl:
                    bonus = {'beginner': "세 영역을 동시에 발전시킬 수 있는 통합 프로그램이 적합합니다",
                             'intermediate': "심화 과정으로 도약할 준비가 되어 있습니다",
                             'advanced': "실전 경험과 전문적 학습으로 전문가 수준에 도달할 수 있습니다"}
                    tips.append(bonus[rl])

                db.session.add(ReadingMBTIType(
                    type_code=type_code,
                    type_name=type_name,
                    reading_level=rl,
                    thinking_level=tl,
                    writing_level=wl,
                    combo_description=combo_desc,
                    full_description=full_desc,
                    reading_style=reading_styles[rl],
                    speaking_style=speaking_styles[tl],
                    writing_style=writing_styles[wl],
                    strengths=strengths if strengths else None,
                    weaknesses=weaknesses if weaknesses else ["현재 특별한 약점은 발견되지 않았습니다"],
                    tips=tips if tips else None,
                    description=full_desc,
                ))

    db.session.commit()
    print("27개 유형 데이터 삽입 완료")
    print("=" * 60)
    print("완료!")
    print("=" * 60)
