# 🛠️ ASO App Workspace — Electric Gun (Stun Gun Simulator)

Thư mục này chứa cấu hình ASO, hồ sơ ứng dụng và pipeline chạy lọc từ khóa cho ứng dụng **Electric Stun Gun Simulator - Taser prank** (`com.real.electric.stun.gun.simulator.taser.prank`).

---

## 📁 Cấu trúc thư mục

```text
apps/ElectricGun/
├── README.md                      (Tài liệu hướng dẫn này)
├── app_config.py                  (Từ khóa, thương hiệu đối thủ, trọng số điểm của ElectricGun)
├── App_Profile.json               (Mô tả hiện tại và đối thủ cạnh tranh chính trên Play Store)
├── run_pipeline.py                (Mã nguồn chạy pipeline lọc từ khóa)
├── Input/                         (Thư mục chứa file CSV từ khóa thô đầu vào)
└── Output/                        (Thư mục chứa các kết quả xuất ra nếu cần thiết)
```

---

## ⚙️ Các bước cấu hình ASO cho ElectricGun

### 1. Cấu hình từ khóa trong `app_config.py`
Mở file `app_config.py` và tinh chỉnh nếu cần:
- **Semantic Groups:**
  - `intent_core_terms`: Chứa các từ khóa cốt lõi như `stun gun`, `taser`, `electric stun gun`, `taser simulator`, `shock gun`, `electric shocker`,...
  - `feature_terms`: Chứa các từ khóa tính năng như `flashlight strobe`, `vibration shock`, `electric shock sounds`, `hair clipper prank`,...
- **Filters:**
  - `competitor_brands`: Thương hiệu đối thủ cần loại trừ (`dmitsoft`, `strategimws`,...).
  - `typo_blacklist`: Các từ sai chính tả phổ biến hoặc vô nghĩa (`tazer`, `tasser`, `teser`,...).

### 2. Điền thông tin cửa hàng trong `App_Profile.json`
Chứa thông tin live store của app và thông tin 2 đối thủ trực tiếp (`com.dmitsoft.stungun` và `com.strategimws.stungunsimulator`) để tính điểm Competitor Boost.

---

## 🚀 Hướng dẫn chạy pipeline lọc từ khóa

Đặt file CSV từ khóa thô (tải từ AppTweak hoặc SensorTower) vào thư mục `apps/ElectricGun/Input/` (ví dụ: `ElectricGun_US_EN.csv`).

Từ thư mục gốc của project `ASO_MVP`, chạy lệnh sau:

### Chạy chế độ tự động xuất Excel:
```powershell
python apps\ElectricGun\run_pipeline.py --csv apps\ElectricGun\Input\ElectricGun_US_EN.csv --market US_EN
```

### Chạy chế độ Web tương tác:
```powershell
python apps\ElectricGun\run_pipeline.py --csv apps\ElectricGun\Input\ElectricGun_US_EN.csv --market US_EN --interactive
```

Kết quả sẽ tự động lưu cùng thư mục với file CSV đầu vào. Báo cáo Excel bao gồm Shortlist 20 Core + 5 Feature + 5 Broad + 10 Consider, biểu đồ phân tích, và chi tiết lý do lọc từng từ khóa.
