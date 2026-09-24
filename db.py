from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")

db = client["skill_swap"]

users = db["users"]
skills = db["skills"]
requests = db["requests"]
messages = db["messages"]
admins = db["admins"]