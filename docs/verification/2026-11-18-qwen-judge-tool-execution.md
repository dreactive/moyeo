# Qwen judge → 기존 도구 실행 검증

검증일: 2026-11-18. 브랜치: `codex/qwen-judge-tool-execution` (기준 `cc6a461`).

## 구현

외부 보조 모델은 LangChain의 엄격한 JSON Schema 출력으로 장소·조건·대상별 의견과 원문 근거를 추출한다. 작성자·메시지·조건 값과 찬반 방향을 코드에서 검증하고, 필요할 때만 관련 과거 메시지 최대 8개로 한 차례 문맥을 보완한다. 도구 권한은 보조 모델에 제공하지 않는다.

각 도구의 준비조건을 독립 확인해 실제 호출만 최대 3개 구성한다. 미지원 응답은 코드로 확인한 기능에만 허용한다. 호출 불가 시 실제 질문·미지원·직접 응답만 후보로 구성한다. 후보를 4개로 채우지 않으며, 0개는 보류하고 1개는 별도 표시한다. 현재 메시지 대상이 우선이고 나머지 호출은 추적에 남는다.

제공된 `submission.judge.judge_prompt`와 `judge_scores`를 그대로 사용한다. Qwen과 LoRA는 원시 yes-minus-no 점수를 산출하고 서비스가 argmax를 선택한다. 채점한 도구명·인자 그대로 기존 RegisteredTools에서 재검증하고 실행한다. 잘못된 점수·예산 초과 입력·실행 실패에는 임의 후보로 대체하지 않는다. 모델 생성은 운영 경로에서 호출하지 않는다.

처리 중 방의 메시지·조건·계획·관측이 바뀌면 실행과 상태 적용을 보류한다. 기존 열린 질문을 보존하고, 아직 일정에 반영되지 않은 장소 ID를 기존 room JSON에 저장해 다음 실행에 복원한다. 새 hard 조건은 소유자 확인 전까지 실제 계산 조건에 넣지 않는다. 과거 계산 결과는 실행별로 다시 계산한다.

## 자동 검증

| 검증 | 결과 |
| --- | --- |
| AI 전체 회귀 | 355 passed |
| Backend 전체 회귀 및 통합, 메모리 DB | 209 passed |
| Frontend 전체 회귀 | 169 passed |
| 명시적 fake/fixture 서비스 시나리오 | 18/18 passed |
| 실제 LangChain 요청 직렬화 및 실패 처리 | MockTransport로 검증, AI 테스트에 포함 |
| 독립 리뷰 후 집중 회귀 | 질문·미처리 장소·오래된 작업 등 34 passed, 전체 회귀에도 포함 |
| Python compileall / git diff --check | 통과 |

Backend 테스트에는 원본 `.env`와 DB를 연결하지 않았다. 프로세스 설정은 `TRIP_ENV_FILE=backend/tests/absent-test.env`, `BACKEND_DB=:memory:`, `AGENT_MODE=fixture`, `COOKIE_SECURE=0`, `TRACE_ENABLED=1`, `SERVE_FRONTEND=1`을 사용했다.

## 실제 Qwen·LoRA와 지도 HTTP 호출

`python -m ai.eval.verify_judge_execution`으로 실제 로컬 모델을 한 번 로드해 네 사례를 검증했다. 보조 입력은 `fixture-audit`으로 명시한 스크립트 입력이며 외부 보조 모델이 생성한 결과가 아니다.

| 사례 | 실제 후보 수 | 원시 점수 | 선택과 결과 | 실행 시간 |
| --- | --- | --- | --- | --- |
| 오동도·여수엑스포 검색 | 2 | 2.202878 / 2.343050 | index 1, 여수엑스포 검색; Kakao HTTP에서 장소 5개 | 671 ms |
| 출발지 정보 부족 | 1 | 1.376933 | 출발지 질문; 도구 미실행 | 88 ms |
| 숙소 예약·결제 요청 | 1 | -7.839903 | 코드가 확인한 미지원 응답; 도구 미실행 | 87 ms |
| 확인된 지역 직접 응답 | 1 | -6.357872 | 여수; 도구 미실행 | 79 ms |

검색 후보는 `query`, `region=여수`, `category=None`을 실제 인자로 제공했다. 선택 인자와 도구 관측 인자의 일치를 스크립트에서 검증했고, trace의 `execution_source=http`를 확인했다. 원문에 없는 예산 100,000원을 의도적으로 보조 입력에 포함했으며 조건 제안에서 제거되는 것도 확인했다.

시간은 모델 로딩과 외부 보조 API를 제외한 각 실행의 측정값이다. 결정 문맥은 각각 1,021 / 735 / 550 / 527자이며 도구 설명·후보를 포함한 전체 judge 프롬프트 길이는 아니다. 단일 후보 사례는 유효 후보의 채점·반환 경로 검증이고 여러 유형 사이 분류 정확도의 증거는 아니다. 원시 점수는 확률이 아니며, 임의 임계값을 사용하지 않는다.

상세 로컬 결과: `.planning/qwen-tool-execution/live-qwen-audit-final.json`. 자동 회귀 로그와 fixture replay 결과도 같은 무시 디렉터리에 보관했다.

## 원본 보존

원본 서버 PID 64600은 계속 실행 중이며 재시작하지 않았다. 방 `_Q-qDpBm`의 원본 DB를 검증용으로 열거나 갱신하지 않았다. 검증 스크립트는 파일을 읽어 SHA-256만 비교했다. 새 모델·토크나이저를 다운로드하거나 가중치를 변경하지 않았다.

검증 전후 동일한 SHA-256:

| 원본 파일 | SHA-256 |
| --- | --- |
| Qwen model.safetensors | `dd924a11b4c220f385b51ffa522daea7c9f3d850e31b162bb5661df483c6d3ee` |
| adapter_model.safetensors | `3e3822a23a7fe781778c3b49d5fdf6cfb8f24245c7120517c6a216efce56a0f8` |
| Qwen config.json | `98d2ff8cc47488d08a2b0b3acf4eb99ef210779b42bd48605f6b8e36acdbf670` |
| tokenizer.json | `c0382117ea329cdf097041132f6d735924b697924d6f6fc3945713e96ce87539` |
| tokenizer_config.json | `5b5d4f65d0acd3b2d56a35b56d374a36cbc1c8fa5cf3b3febbbfabf22f359583` |
| adapter_config.json | `ca117b489997e19f03dccbf0d559e54e4dd65166525a0fc72152f1cff75ccb36` |
| candidate-preview.sqlite3 | `a323c391ea3e7af3032f0dcb1fbabbe3ff25cc30aec4c7a2c571655dee786b43` |

## 외부 보조 모델 설정과 한계

새 작업 공간의 무시된 `.env`에 `AUX_MODEL=gpt-6-luna`, `AUX_REASONING_EFFORT=none`, `AUXILIARY_BACKEND=external`, 빈 `OPENAI_API_KEY=`를 기록했다. `OPEN_AI_API_KEY`는 잘못된 이름이다. 기존 지도 공급자 설정은 보존하고 실제 `.env`는 Git에 넣지 않았다.

선정 근거는 [공식 모델 문서](https://developers.openai.com/api/docs/models/gpt-6-luna)의 짧고 반복적인 작업에 적합한 특성과 구조화 출력 지원이다. Chat Completions의 함수 호출은 reasoning effort none 조건이 있으므로 추론을 끄도록 설정했다. 키 변수명은 [공식 Quickstart](https://developers.openai.com/api/docs/quickstart)와 일치한다. 계정의 모델 접근 권한은 키 설정 후 확인해야 한다.

API 키가 없어 **실제 외부 보조 모델의 한국어 추출 품질·지연 및 전체 외부 보조 → Qwen → 도구 경로는 실검증하지 않았다.** 실제 LangChain 클라이언트의 JSON Schema strict 요청, 추론 옵션, 서비스 도구 미바인딩, 비밀값을 노출하지 않는 오류 처리는 MockTransport로 확인했다. 키가 없으면 명시적인 실패 기록을 남기며 fixture로 자동 전환하지 않는다.


## 추가 검증: 이전에 고른 두 장소의 상세 정보

사용자가 제공한 `auxiliary-qwen-two-places.json`을 해당 파일 그대로 검증 fixture에 복사하고, `ai/eval/context_requests.py`에서 실제 스키마로 변환했다. 원본 checkout의 JSON과 설명 문서는 수정하지 않았다. 설명 문서의 `gpt-luna-6` 명칭은 실행 모델 ID로 사용하지 않았다.

1. 1차 합성 보조 출력은 현재 `m102/u1`의 “아까 내가 고른 두 곳 상세 정보 보여줘.”를 미해결 조회 요청으로 구조화한다. 최소 입력에는 세 장소의 이름·참조만 있고 사용자별 선택 관계나 전체 관측 본문은 없다.
2. 관련 과거 기록 `m101/u1` 한 개만 추가한다. “대전시립미술관 말고 한밭수목원하고 엑스포과학공원으로 하자.”의 두 대상·배제 인용을 보존하고 1차 사실을 재사용한다. 다른 작성자의 같은 장소 언급은 선택 근거로 쓰지 않는다.
3. 코드는 같은 방의 기존 `search-result-1`로 `get_place_details({place_ref:p1})`, `get_place_details({place_ref:p2})`만 완성한다. `p3`는 제외한다. 과거 문장은 현재의 새 찬반이나 새 항목으로 등록하지 않는다.
4. **실제 Qwen·LoRA**의 첫 점수는 **0.841249 / 1.081180**, 선택은 **index 1, p2**였다. 기존 RegisteredTools가 같은 인자로 한 번 실행하고, 상태에는 `completed_refs=[p2]`, `pending_refs=[p1]`이 남았다.
5. 다음 판단에는 **p1 한 후보**만 제공했다. 실제 점수 **0.965215**, 선택 index 0으로 p1을 실행했다. 최종 상태는 `completed`, 미처리 대상은 0개다. 보조 입력에는 추천 순위·정답·예시 점수를 넣지 않았다.

실행 명령:

```powershell
python -m ai.eval.verify_context_requests --base-model PATH_TO_BASE --adapter PATH_TO_ADAPTER_DIRECTORY --database PATH_TO_EXISTING_DB --output .planning/qwen-tool-execution/context-qwen-audit-final.json
```

| 항목 | 결과 |
| --- | --- |
| 합성 보조 1차·2차, 관련 기록 보완 | 통과: 각 1회, m101만 추가 |
| 실제 Qwen 후보 비교 | 통과: 후보 2개 → 1개, 유한 점수·범위·argmax 일치 |
| 기존 실행기의 인자·결과·요청 상태 | 통과: p2 → p1, 회차별 1회 |
| 공급자 경로 | **fixture**: 합성 p1/p2 결과, 외부 HTTP 호출 아님 |
| 원본 DB·가중치 해시 | 검증 전후 동일 |
| 실제 외부 보조 API | **미실행**: 빈 OPENAI_API_KEY, gpt-6-luna 미호출 |

최종 실행은 모델 로딩 6.72초, 두 단계 및 두 판단·종료까지 3.21초였다. 합성 보조·공급자를 사용한 통합 측정이며 실제 외부 보조·장소 API 지연의 증거는 아니다. 상세 후보·점수·인자·인용·실행 결과·전후 상태는 위 JSON에 기록했다.

회차 제한 후 남은 요청은 room JSON에 저장해 별도 실행으로 복원하는 테스트도 통과했다. 저장된 완료 상태는 유지하고, 새 독립 검색이 이전 상세 조회에 가려지지 않는다. 같은 사용자가 명시적으로 대상을 제외하거나 기존 미해결 요청을 해결하면 이전 요청을 `superseded`로 남겨 다시 실행하지 않는다. 캐시 유무에 따른 실제 도구 실행과 상태 보존도 검증했다.
