import pandas as pd
import numpy as np

# Số mẫu muốn tạo
N = 2000

np.random.seed(42)

# Tuổi 20-90
age = np.random.randint(20, 91, N)

# Giới tính 0=nữ, 1=nam
gender = np.random.randint(0, 2, N)

# Nhịp tim trung bình (bpm)
heart_rate_avg = np.random.normal(75, 15, N).astype(int)  # mean 75, std 15

# SpO2 (%)
spo2_avg = np.random.normal(97, 2, N).astype(int)  # mean 97%, std 2%

# Nhãn bệnh dựa trên rule đơn giản:
# Nếu HR > 100 hoặc SpO2 < 92 hoặc tuổi > 70 → nguy cơ = 1, else 0
label = ((heart_rate_avg > 100) | (spo2_avg < 92) | (age > 70)).astype(int)

# Tạo DataFrame
df = pd.DataFrame({
    "age": age,
    "gender": gender,
    "heart_rate_avg": heart_rate_avg,
    "spo2_avg": spo2_avg,
    "label": label
})

# Lưu CSV
df.to_csv("patient_data.csv", index=False)
print("[✓] CSV patient_data.csv đã tạo xong!")
