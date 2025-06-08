import pickle

# Đường dẫn tới file pickle
file_path = 'app/embeddings.pkl'

# Đọc dữ liệu từ file
with open(file_path, 'rb') as file:
    data = pickle.load(file)

# Hiển thị nội dung
print(data)
