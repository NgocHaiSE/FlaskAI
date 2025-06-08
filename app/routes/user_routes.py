from flask import Blueprint, jsonify, request
from app.config import Config
import mysql.connector

user_bp = Blueprint('user', __name__)

@user_bp.route('/login', methods=['POST'])
def login():
  try:
    
    

