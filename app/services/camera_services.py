import subprocess
import os

dict_processes = {}

path = os.path.join('app', 'utils', 'AI_process.py')

def start(id):
  process = subprocess.Popen(['python', path, str(id)])
  dict_processes[id] = process
  
def check(id):
  if id in dict_processes:
    status = dict_processes[id].poll()
    if status is None:
      print("Tiến trình đang chạy.")
      return True
    else:
      print(f"Tiến trình đã kết thúc với mã trạng thái: {status}")
      return False
  else:
    print("Không tồn tại tiến trình: ", id)
    return False
  
def stop(id):
  if int(id) in dict_processes:
        dict_processes[int(id)].terminate()
        return f"Đã kết thúc tiến trình {id}",200
  elif id in dict_processes:
        dict_processes[id].terminate()
        return f"Đã kết thúc tiến trình {id}",200
  else:
        return f"Tiến trình {id} không tồn tại",200
    