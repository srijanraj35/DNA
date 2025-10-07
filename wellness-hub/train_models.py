import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
import pickle
import os

# Generate synthetic training data
np.random.seed(42)
data = pd.DataFrame({
    'sleep_hours': np.random.randint(4, 10, 100),
    'work_hours': np.random.randint(6, 12, 100),
    'physical_activity': np.random.randint(0, 2, 100),
    'critical_incident': np.random.randint(0, 2, 100),
    'stress_level': np.random.randint(1, 11, 100)
})

# Target classification: Low (1-3), Moderate (4-6), Elevated (7-8), High (9-10)
def stress_class(level):
    if level <= 3: return 0  # Low
    if level <= 6: return 1  # Moderate
    if level <= 8: return 2  # Elevated
    return 3                  # High

data['stress_class'] = data['stress_level'].apply(stress_class)

# Features and target
X = data[['sleep_hours', 'work_hours', 'physical_activity', 'critical_incident']]
y = data['stress_class']

# Train model
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# Save model
os.makedirs('models', exist_ok=True)
with open('models/stress_model.pkl', 'wb') as f:
    pickle.dump(model, f)

print("ML model trained and saved to models/stress_model.pkl")

