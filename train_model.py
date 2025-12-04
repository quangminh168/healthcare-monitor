import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
import joblib
from sklearn.metrics import classification_report

# Load dữ liệu
df = pd.read_csv("patient_data.csv")

X = df[["age", "gender", "heart_rate_avg", "spo2_avg"]]
y = df["label"]

# Chia train/test
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# Train model
model = RandomForestClassifier(n_estimators=200, random_state=42)
model.fit(X_train, y_train)

# Đánh giá
preds = model.predict(X_test)
probs = model.predict_proba(X_test)[:, 1]

print(classification_report(y_test, preds))

# Lưu model
joblib.dump(model, "patient_model.pkl")
print("[✓] Model patient_model.pkl đã lưu thành công!")
