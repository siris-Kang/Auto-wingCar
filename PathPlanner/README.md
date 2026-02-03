# ROS2 Nav2 Path Planning 교체용 경로 생성 가이드 

ROS2 **Nav2의 경로 생성(Path Planning) 단계**를 커스텀 Towing Car 플래너로 대체한다.
**장애물맵 생성 → 경로 탐색 → 경로 저장 → 시각화**의 과정이 있다.
생성된 경로(JSON)는 RC카가 실제 주행 시 따라갈 수 있도록 저장한다.

---

## 개요

### 처리 파이프라인
1. 마스크 기반 장애물맵(가상 장애물 포함) 생성
2. 노드(Start/Goal)와 장애물(ox/oy)을 입력으로 경로 탐색 수행
3. 결과 경로를 JSON 파일로 저장
4. 시각화로 결과 검증

---

## edge01 시나리오

### Start / Goal 정의
- **Start01**
  - `x: 84`, `y: 20` (pixel 기준)
- **Goal01**
  - `x: 115`, `y: 206`

> 참고: `x, y` 좌표는 `node.json` 및 사용 중인 맵 좌표계 정의와 일관되어야 한다.
> json에서는 정수 단위로 변환하여 입력해야한다.

---

## 1) 장애물맵 생성

마스크 이미지(라이다로 인식이 어려운 구역/가상 장애물 포함)와 맵 YAML을 이용해  
플래너 입력용 장애물 좌표(`ox`, `oy`)를 생성한다.

```
julia apps/make_obstaclemap.jl --mask maps/edge01/mask.png --map_yaml maps/my_map.yaml --out_dir maps/edge01 --prefix edge01
```

### 입력
- `maps/edge01/mask.png`  
  - 가상 장애물(라이더로 인식하지 못하는 벽 등)을 포함한 마스크 이미지
- `maps/my_map.yaml`  
  - 기본 지도 메타 정보(YAML)

### 출력(예시)
- `maps/edge01/edge01_oxoy.json`  
  - 장애물 좌표(ox/oy) JSON
- `maps/edge01/edge01_*.png`  
  - 디버깅/검증용 맵 이미지


---

## 2) 경로 탐색 실행

생성된 장애물 좌표(`oxoy`)와 노드 정의(`node.json`)를 입력으로 경로 탐색을 수행한다.  
탐색 결과는 경로 JSON 파일로 저장되며, 추가로 로그가 기록된다.

```
julia apps/path_planning.jl --nodes maps/edge01/node.json --oxoy maps/edge01/edge01_oxoy.json --pairs upper --out_dir maps/edge01/paths --log_dir maps/edge01/planner_logs
```

### 입력
- `maps/edge01/node.json`  
  - Start/Goal 노드 정의(좌표 및 필요 시 yaw 포함)
- `maps/edge01/edge01_oxoy.json`  
  - 장애물 좌표(ox/oy)

### 출력
- `maps/edge01/paths/path_S01_to_G01_YYYYMMDD_HHMMSS.json`  
  - 생성된 경로(JSON)  
  - 예시: `path_S01_to_G01_20260202_173003.json`
- `maps/edge01/planner_logs/*`  
  - 탐색 로그


## 3) 시각화
- 장애물 포인트(ox/oy)
- Start/Goal 위치
- 생성된 경로(waypoints)

```
python apps/viz_paths.py --path_file maps/edge01/paths/path_S01_to_G01_20260202_173003.json --oxoy_json maps/edge01/edge01_oxoy.json --nodes maps/edge01/node.json --show
```

---

## 산출물

RC카 실제 주행에 활용하는 핵심 산출물은 아래 경로 파일이다.

- `maps/edge01/paths/path_S01_to_G01_*.json`
