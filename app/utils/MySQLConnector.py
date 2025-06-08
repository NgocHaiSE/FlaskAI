import mysql.connector

def getConnector():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",        
        password="08032003",    
        database="face_application"      
        )
    return conn