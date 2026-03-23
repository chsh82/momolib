# -*- coding: utf-8 -*-
"""
MOMOLIB 논술 첨삭 서비스 (Claude API 기반)
MOMOAI momoai_service.py 에서 이식 및 단순화
"""
import os
import re
import time
import threading
from datetime import datetime
import anthropic

_semaphore = threading.Semaphore(2)  # 동시 처리 최대 2개


SYSTEM_PROMPT_STANDARD = """당신은 MOMOLIB의 전문 논술 첨삭 강사입니다.
학생의 논술문을 분석하고 아래 형식에 맞는 HTML 첨삭 리포트를 생성합니다.

## 첨삭 리포트 HTML 형식

반드시 다음 구조를 포함한 완전한 HTML을 생성하세요:

```html
<!DOCTYPE html>
<html lang="ko">
<head><meta charset="UTF-8"><title>첨삭 리포트</title>
<style>
  body { font-family: 'Noto Sans KR', sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; color: #333; }
  .header { background: #4f46e5; color: white; padding: 24px; border-radius: 12px; margin-bottom: 24px; }
  .score-box { display: inline-block; background: white; color: #4f46e5; padding: 8px 20px; border-radius: 8px; font-size: 2em; font-weight: bold; margin-left: 16px; }
  .grade-box { display: inline-block; background: #818cf8; color: white; padding: 8px 16px; border-radius: 8px; font-size: 1.2em; margin-left: 8px; }
  .section { background: white; border: 1px solid #e5e7eb; border-radius: 12px; padding: 20px; margin-bottom: 20px; }
  .section h2 { color: #4f46e5; border-bottom: 2px solid #e0e7ff; padding-bottom: 8px; margin-top: 0; }
  .score-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
  .score-item { background: #f5f3ff; border-radius: 8px; padding: 12px; text-align: center; }
  .score-item .label { font-size: 0.85em; color: #6b7280; }
  .score-item .value { font-size: 1.4em; font-weight: bold; color: #4f46e5; }
  .highlight-good { background: #dcfce7; border-left: 4px solid #16a34a; padding: 12px; border-radius: 4px; margin: 8px 0; }
  .highlight-improve { background: #fef9c3; border-left: 4px solid #ca8a04; padding: 12px; border-radius: 4px; margin: 8px 0; }
  .original-text { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; white-space: pre-wrap; line-height: 1.8; }
  .corrected-text { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 16px; white-space: pre-wrap; line-height: 1.8; }
  ins { background: #bbf7d0; text-decoration: none; }
  del { background: #fee2e2; text-decoration: line-through; color: #dc2626; }
  .total-score { font-size: 2.5em; font-weight: bold; color: #4f46e5; }
</style></head>
<body>

<div class="header">
  <h1>📝 논술 첨삭 리포트</h1>
  <div>총점 <span class="score-box" id="total-score">XX</span> 점
       등급 <span class="grade-box" id="final-grade">X등급</span></div>
</div>

<!-- 1. 원문 -->
<div class="section">
  <h2>원문</h2>
  <div class="original-text">[원문 내용]</div>
</div>

<!-- 2. 첨삭문 (ins/del 태그로 수정 표시) -->
<div class="section">
  <h2>첨삭문</h2>
  <div class="corrected-text">[첨삭된 내용 - ins/del 태그 활용]</div>
</div>

<!-- 3. 사고유형 점수 (9개) -->
<div class="section">
  <h2>사고유형 분석</h2>
  <div class="score-grid">
    <div class="score-item"><div class="label">요약</div><div class="value" id="score-요약">X</div></div>
    <div class="score-item"><div class="label">비교</div><div class="value" id="score-비교">X</div></div>
    <div class="score-item"><div class="label">적용</div><div class="value" id="score-적용">X</div></div>
    <div class="score-item"><div class="label">평가</div><div class="value" id="score-평가">X</div></div>
    <div class="score-item"><div class="label">비판</div><div class="value" id="score-비판">X</div></div>
    <div class="score-item"><div class="label">문제해결</div><div class="value" id="score-문제해결">X</div></div>
    <div class="score-item"><div class="label">자료해석</div><div class="value" id="score-자료해석">X</div></div>
    <div class="score-item"><div class="label">견해제시</div><div class="value" id="score-견해제시">X</div></div>
    <div class="score-item"><div class="label">종합</div><div class="value" id="score-종합">X</div></div>
  </div>
</div>

<!-- 4. 통합지표 점수 (9개) -->
<div class="section">
  <h2>통합지표 분석</h2>
  <div class="score-grid">
    <div class="score-item"><div class="label">결론</div><div class="value" id="score-결론">X</div></div>
    <div class="score-item"><div class="label">구조/논리</div><div class="value" id="score-구조논리">X</div></div>
    <div class="score-item"><div class="label">표현/명료</div><div class="value" id="score-표현명료">X</div></div>
    <div class="score-item"><div class="label">문제인식</div><div class="value" id="score-문제인식">X</div></div>
    <div class="score-item"><div class="label">개념/정보</div><div class="value" id="score-개념정보">X</div></div>
    <div class="score-item"><div class="label">목적/적절성</div><div class="value" id="score-목적적절">X</div></div>
    <div class="score-item"><div class="label">관점/다각성</div><div class="value" id="score-관점다각">X</div></div>
    <div class="score-item"><div class="label">심층성</div><div class="value" id="score-심층성">X</div></div>
    <div class="score-item"><div class="label">완전성</div><div class="value" id="score-완전성">X</div></div>
  </div>
</div>

<!-- 5. 잘한 점 -->
<div class="section">
  <h2>✅ 잘한 점</h2>
  [잘한 점 3가지 이상]
</div>

<!-- 6. 개선할 점 -->
<div class="section">
  <h2>💡 개선할 점</h2>
  [개선할 점 3가지 이상]
</div>

<!-- 7. 총평 -->
<div class="section">
  <h2>📋 총평</h2>
  [총평 2~3 문단]
</div>

</body></html>
```

위 형식을 반드시 준수하며, id 속성의 점수값을 실제 숫자로 채우세요.
총점은 100점 만점, 각 지표는 10점 만점입니다.
등급은 A+(95↑) A(90↑) B+(85↑) B(80↑) C+(75↑) C(70↑) D+(65↑) D(60↑) F(60미만) 입니다."""


SYSTEM_PROMPT_ELEMENTARY = """당신은 MOMOLIB의 초등학생 전담 논술 선생님입니다.
초등학교 1~6학년 학생들의 글쓰기를 아이 눈높이에 맞게 따뜻하고 격려하는 방식으로 첨삭합니다.

위 STANDARD 프롬프트와 동일한 HTML 형식을 사용하되:
- 총평과 피드백은 쉬운 언어로, 따뜻하고 응원하는 어투로 작성
- 등급 대신 성장단계: 씨앗🌱 / 새싹🌿 / 꽃봉오리🌸 / 꽃🌺 / 열매🍎
- 점수는 10점 만점 유지
- 교정 표현은 최대한 긍정적으로"""


def _parse_score(html_content: str):
    """HTML에서 총점과 등급 파싱"""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')

        # 총점
        score_el = soup.find(id='total-score')
        total_score = None
        if score_el:
            m = re.search(r'[\d.]+', score_el.get_text())
            if m:
                total_score = float(m.group())

        # 등급
        grade_el = soup.find(id='final-grade')
        final_grade = grade_el.get_text(strip=True) if grade_el else None

        return total_score, final_grade
    except Exception:
        return None, None


def correct_essay(essay_id: str, api_key: str = None):
    """
    에세이 AI 첨삭 실행 (백그라운드 스레드에서 호출)

    Args:
        essay_id: Essay.essay_id
        api_key: Anthropic API key (없으면 환경변수 사용)
    """
    from app import create_app
    from app.models import db
    from app.models.essay import Essay, EssayVersion, EssayResult
    import os

    app = create_app(os.environ.get('FLASK_ENV', 'development'))

    with app.app_context():
        essay = Essay.query.get(essay_id)
        if not essay:
            return

        essay.status = 'processing'
        db.session.commit()

        try:
            _semaphore.acquire()

            key = api_key or os.environ.get('ANTHROPIC_API_KEY', '')
            client = anthropic.Anthropic(api_key=key)

            system = (SYSTEM_PROMPT_ELEMENTARY
                      if essay.correction_model == 'elementary'
                      else SYSTEM_PROMPT_STANDARD)

            user_msg = f"제목: {essay.title}\n학년: {essay.grade or '미입력'}\n\n"
            if essay.teacher_guide:
                user_msg += f"[강사 가이드]\n{essay.teacher_guide}\n\n"
            user_msg += f"[논술 원문]\n{essay.original_text}"

            max_tokens = 4096 if essay.correction_model == 'elementary' else 8192

            response = client.messages.create(
                model='claude-sonnet-4-6',
                max_tokens=max_tokens,
                system=system,
                messages=[{'role': 'user', 'content': user_msg}],
            )

            html_content = response.content[0].text

            # 버전 생성
            version_number = (essay.current_version or 0) + 1
            version = EssayVersion(
                essay_id=essay_id,
                version_number=version_number,
                html_content=html_content,
            )
            db.session.add(version)
            db.session.flush()

            # 점수 파싱
            total_score, final_grade = _parse_score(html_content)

            # 결과 생성/업데이트
            if essay.result:
                essay.result.version_id = version.version_id
                essay.result.total_score = total_score
                essay.result.final_grade = final_grade
            else:
                result = EssayResult(
                    essay_id=essay_id,
                    version_id=version.version_id,
                    total_score=total_score,
                    final_grade=final_grade,
                )
                db.session.add(result)

            essay.current_version = version_number
            essay.status = 'reviewing'
            essay.completed_at = datetime.utcnow()
            db.session.commit()

        except anthropic.RateLimitError:
            time.sleep(60)
            essay.status = 'failed'
            db.session.commit()
        except Exception as e:
            essay.status = 'failed'
            db.session.commit()
            raise
        finally:
            _semaphore.release()
