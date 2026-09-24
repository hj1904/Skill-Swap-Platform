# Flask + MongoDB + Sessions + Search + Requests + Admin

from flask import Flask, render_template, request, redirect, session, send_from_directory
from pymongo import MongoClient
from bson.objectid import ObjectId
import os
from flask import flash

app = Flask(__name__)
app.secret_key = "skillswap_secret"

# MongoDB Connection

client = MongoClient("mongodb://localhost:27017/")
db = client["skill_swap"]

users = db["users"]
skills = db["skills"]
requests_db = db["requests"]
admins = db["admins"]

# Upload Folder

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# HOME

@app.route("/")
def home():
    return render_template("index.html")

# REGISTER PAGE

@app.route("/register")
def register():
    return render_template("register.html")

# REGISTER USER

@app.route("/register_user", methods=["POST"])
def register_user():

    name = request.form["name"]
    email = request.form["email"]
    password = request.form["password"]

    file = request.files["photo"]

    filename = file.filename

    if filename != "":
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
    else:
        filename = "default.png"

    users.insert_one({
        "name": name,
        "email": email,
        "password": password,
        "photo": filename
    })

    return redirect("/login")

# LOGIN PAGE

@app.route("/login")
def login():
    return render_template("login.html")


# LOGIN USER

@app.route("/login_user", methods=["POST"])
def login_user():

    user = users.find_one({
        "email": request.form["email"],
        "password": request.form["password"]
    })

    if user:
        session["user_id"] = str(user["_id"])
        return redirect("/dashboard")

    flash("Invalid email or password!")   # 👈 error message
    return redirect("/login")

## user_profile
@app.route("/profile/<id>")
def user_profile(id):

    if "user_id" not in session:
        return redirect("/login")

    user = users.find_one({
        "_id": ObjectId(id)
    })

    teach_skills = list(skills.find({
        "user_id": id,
        "type": "teach"
    }))

    learn_skills = list(skills.find({
        "user_id": id,
        "type": "learn"
    }))

    connections = requests_db.count_documents({
        "$or":[
            {"sender_id": id, "status":"accepted"},
            {"receiver_id": id, "status":"accepted"}
        ]
    })

    return render_template(
        "user_profile.html",
        user=user,
        teach_skills=teach_skills,
        learn_skills=learn_skills,
        connections=connections
    )
## Edit User Profile
@app.route("/edit_profile")
def edit_profile():

    if "user_id" not in session:
        return redirect("/login")

    user = users.find_one({
        "_id": ObjectId(session["user_id"])
    })

    return render_template("edit_profile.html", user=user)
##Updated user profile
from flask import flash
import os
from werkzeug.utils import secure_filename

@app.route("/update_profile", methods=["POST"])
def update_profile():

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    name = request.form["name"]
    email = request.form["email"]
    username = request.form["username"]
    password = request.form["password"]

    data = {
        "name": name,
        "email": email,
        "username": username
    }

    # password update only if entered
    if password.strip() != "":
        data["password"] = password

        os.makedirs("static/uploads", exist_ok=True)

        file = request.files["photo"]

        if file.filename != "":
            filename = secure_filename(file.filename)

            file.save(os.path.join("static/uploads", filename))

            data["photo"] = filename   # ✅ ONLY filename

            # update database
            users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": data}
            )

            flash("Profile Updated Successfully ")

            return redirect("/profile")

# DASHBOARD

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect("/login")

    current_user = session["user_id"]

    # Fetch latest user data every time
    user = users.find_one({
        "_id": ObjectId(current_user)
    })

    # Dynamic Counts
    skills_count = skills.count_documents({
        "user_id": current_user
    })

    sent_count = requests_db.count_documents({
        "sender_id": current_user
    })

    connections_count = requests_db.count_documents({
        "$or": [
            {"sender_id": current_user, "status": "accepted"},
            {"receiver_id": current_user, "status": "accepted"}
        ]
    })

    return render_template(
        "dashboard.html",
        user=user,
        skills_count=skills_count,
        sent_count=sent_count,
        connections_count=connections_count
    )

# ADD SKILL

@app.route("/add_skill", methods=["POST"])
def add_skill():

    if "user_id" not in session:
        return redirect("/login")

    current_user = session["user_id"]

    skill_name = request.form["skill_name"].strip()
    skill_type = request.form["type"]

    # Check if already exists
    existing = skills.find_one({
        "user_id": current_user,
        "skill_name": {"$regex": f"^{skill_name}$", "$options": "i"},
        "type": skill_type
    })

    if existing:
        flash("Skill already added!")
        return redirect("/dashboard")

    # Insert new skill
    skills.insert_one({
        "user_id": current_user,
        "skill_name": skill_name,
        "type": skill_type
    })

    flash("Skill added successfully!")

    return redirect("/dashboard")

# SEARCH PAGE

@app.route("/search", methods=["GET", "POST"])
def search():

    if "user_id" not in session:
        return redirect("/login")

    current_user = str(session["user_id"])

    results = []
    searched = False

    if request.method == "POST":

        searched = True
        keyword = request.form["skill"]

        data = skills.find({
            "skill_name": {"$regex": keyword, "$options": "i"},
            "type": "teach"
        })

        for item in data:

            if str(item["user_id"]) == current_user:
                continue

            teacher = users.find_one({
                "_id": ObjectId(item["user_id"])
            })

            req = requests_db.find_one({
                "sender_id": current_user,
                "receiver_id": str(item["user_id"]),
                "skill_id": str(item["_id"])
            })

            status = "none"

            if req:
                status = req["status"]

            results.append({
                "_id": str(item["_id"]),
                "skill_name": item["skill_name"],
                "user_id": item["user_id"],
                "name": teacher["name"],
                "photo": teacher.get("photo", ""),
                "status": status
            })

    return render_template(
        "search.html",
        skills=results,
        searched=searched
    )

# SEND REQUEST

from flask import flash

@app.route("/send_request", methods=["POST"])
def send_request():

    if "user_id" not in session:
        return redirect("/login")

    sender_id = str(session["user_id"])
    receiver_id = str(request.form["receiver_id"])
    skill_id = str(request.form["skill_id"])

    # duplicate check
    existing = requests_db.find_one({
        "sender_id": sender_id,
        "receiver_id": receiver_id,
        "skill_id": skill_id
    })

    if not existing:
        requests_db.insert_one({
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "skill_id": skill_id,
            "status": "pending"
        })

    flash("Request Sent Successfully ")

    return redirect("/search")

# REQUEST PAGE

@app.route("/requests")
def requests_page():

    if "user_id" not in session:
        return redirect("/login")

    current_user = str(session["user_id"])

    # Incoming
    incoming_data = requests_db.find({
        "receiver_id": current_user
    })

    incoming = []

    for r in incoming_data:

        sender = users.find_one({
            "_id": ObjectId(r["sender_id"])
        })

        skill = skills.find_one({
            "_id": ObjectId(r["skill_id"])
        })

        if sender and skill:
            incoming.append({
                "_id": str(r["_id"]),
                "name": sender["name"],
                "photo": sender["photo"],
                "skill": skill["skill_name"],
                "status": r["status"]
            })

    # Sent
    sent_data = requests_db.find({
        "sender_id": current_user
    })

    sent = []

    for r in sent_data:

        receiver = users.find_one({
            "_id": ObjectId(r["receiver_id"])
        })

        skill = skills.find_one({
            "_id": ObjectId(r["skill_id"])
        })

        if receiver and skill:
            sent.append({
                "name": receiver["name"],
                "photo": receiver["photo"],
                "skill": skill["skill_name"],
                "status": r["status"]
            })

    return render_template(
        "requests.html",
        incoming=incoming,
        sent=sent
    )

# ACCEPT / REJECT REQUEST

@app.route("/update_request", methods=["POST"])
def update_request():

    req_id = request.form["id"]
    status = request.form["status"]

    requests_db.update_one(
        {"_id": ObjectId(req_id)},
        {"$set": {"status": status}}
    )

    flash(f"Request {status} successfully!")   # 👈 popup message

    return redirect("/requests")


# PROFILE PAGE

@app.route("/profile")
def profile():

    if "user_id" not in session:
        return redirect("/login")

    current_user = session["user_id"]

    user = users.find_one({
        "_id": ObjectId(current_user)
    })

    teach_skills = list(skills.find({
        "user_id": current_user,
        "type": "teach"
    }))

    learn_skills = list(skills.find({
        "user_id": current_user,
        "type": "learn"
    }))

    sent_count = requests_db.count_documents({
        "sender_id": current_user
    })

    received_count = requests_db.count_documents({
        "receiver_id": current_user
    })

    connections = requests_db.count_documents({
        "$or":[
            {"sender_id": current_user, "status":"accepted"},
            {"receiver_id": current_user, "status":"accepted"}
        ]
    })

    return render_template(
        "profile.html",
        user=user,
        teach_skills=teach_skills,
        learn_skills=learn_skills,
        sent_count=sent_count,
        received_count=received_count,
        connections=connections
    )


# BROWSE USERS

@app.route("/browse")
def browse():

    all_users = users.find()

    return render_template(
        "browse.html",
        users=all_users
    )

# ==========================
# ADMIN LOGIN PAGE
# ==========================
@app.route("/admin")
def admin():
    return render_template("admin_login.html")


# ADMIN LOGIN

@app.route("/admin_login", methods=["POST"])
def admin_login():

    email = request.form["email"]
    password = request.form["password"]

    admin_user = admins.find_one({
        "email": email,
        "password": password
    })

    if admin_user:
        session["admin"] = "yes"
        return redirect("/admin_dashboard")

    return "Invalid Admin Login"


# ADMIN DASHBOARD

@app.route("/admin_dashboard")
def admin_dashboard():

    if "admin" not in session:
        return redirect("/admin")

    user_list = list(users.find())
    skill_list = []
    request_list = []

    # 🔹 Skills with user names
    for s in skills.find():
        u = users.find_one({"_id": ObjectId(s["user_id"])})
        skill_list.append({
            "_id": s["_id"],
            "skill_name": s["skill_name"],
            "type": s["type"],
            "user_name": u["name"] if u else "Unknown"
        })

    # 🔹 Requests with names
    for r in requests_db.find():
        sender = users.find_one({"_id": ObjectId(r["sender_id"])})
        receiver = users.find_one({"_id": ObjectId(r["receiver_id"])})
        skill = skills.find_one({"_id": ObjectId(r["skill_id"])})

        request_list.append({
            "_id": r["_id"],
            "sender": sender["name"] if sender else "Unknown",
            "receiver": receiver["name"] if receiver else "Unknown",
            "skill": skill["skill_name"] if skill else "Skill",
            "status": r["status"]
        })

    return render_template(
        "admin_dashboard.html",
        users=user_list,
        skills=skill_list,
        requests=request_list
    )

# LOGOUT USER

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# IMAGE SHOW

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )
## Delete User (Admin)
@app.route("/delete_user", methods=["POST"])
def delete_user():

    if "admin" not in session:
        return redirect("/admin")

    user_id = request.form["id"]

    users.delete_one({"_id": ObjectId(user_id)})

    # remove related data
    skills.delete_many({"user_id": user_id})
    requests_db.delete_many({"sender_id": user_id})
    requests_db.delete_many({"receiver_id": user_id})

    return redirect("/admin_dashboard")

## Delete Skill (Admin)
@app.route("/delete_skill", methods=["POST"])
def delete_skill():

    if "admin" not in session:
        return redirect("/admin")

    skill_id = request.form["id"]

    skills.delete_one({"_id": ObjectId(skill_id)})

    return redirect("/admin_dashboard")

## Update Skill (Admin)
@app.route("/update_skill", methods=["POST"])
def update_skill():

    if "admin" not in session:
        return redirect("/admin")

    skill_id = request.form["id"]
    new_name = request.form["skill_name"]

    skills.update_one(
        {"_id": ObjectId(skill_id)},
        {"$set": {"skill_name": new_name}}
    )

    return redirect("/admin_dashboard")
## DELETE REQUEST (Admin)
@app.route("/delete_request", methods=["POST"])
def delete_request():

    if "admin" not in session:
        return redirect("/admin")

    req_id = request.form["id"]

    requests_db.delete_one({
        "_id": ObjectId(req_id)
    })

    flash("Request deleted successfully ✅")

    return redirect("/admin_dashboard")
# ==========================
# RUN
# ==========================
if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)