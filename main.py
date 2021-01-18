import os
from dotenv import load_dotenv
from flask import Flask, render_template, request,send_file
from random import choice
from flask import Flask, flash, jsonify, redirect, render_template, request, session,url_for, json, g
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
import sqlite3
import nexmo
import azure
import json
from datetime import date
from azure.core.exceptions import ResourceNotFoundError
from azure.ai.formrecognizer import FormRecognizerClient
from azure.ai.formrecognizer import FormTrainingClient
from azure.core.credentials import AzureKeyCredential
print(os.getenv("REPLIT_DB_URL"))
import pandas as pd

# FILE 
# Create your connection.
cnx = sqlite3.connect('database.db')
df = pd.read_sql_query("SELECT * FROM receipts", cnx)
df.to_csv (r'receipts.csv', index = False, header=True)
cnx.commit()
cnx.close()

print(df)
# AZURE KEYS
endpoint = "https://jurasa.cognitiveservices.azure.com/"
key = "aa94a7778a2c4563b4ab4af398738ab5" 
form_recognizer_client = FormRecognizerClient(endpoint, AzureKeyCredential(key))


client = nexmo.Client(key='e20bd8c1', secret='2esQ66LEO6TSLIvd')

web_site = Flask(__name__)
secretkey = os.urandom(24)
web_site.secret_key = secretkey

#sqlite3 database
DATABASE = 'database.db'

## query function we will use
def query_db(query, args=(), one=False):
  connection = sqlite3.connect(DATABASE, check_same_thread=False)
  cur = connection.cursor() 
  cur.execute(query, args)
  data = cur.fetchall()
  connection.commit()
  connection.close()
  return (data[0] if data else None) if one else data

@web_site.teardown_appcontext
def close_connection(exception):
  db = getattr(g, '_database', None)
  if db is not None:
    db.close()
##makes querying less messy
##structure of query will be like users = query_db("SELECT * FROM users")

##process service function
##literal black magic
def process_service(service):
  pdate = service[6]
  dmax = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
  interval = service[4]
  intv = interval
  interval_type = service[5]
  if interval_type == 'days':
    intv = pdate.day + interval
    while intv > dmax[pdate.month -1]:
      intv -= dmax[pdate.month -1] - pdate.day + 1
      pdate.day = 1
      if pdate.month == 12:
        pdate.month = 1
        pdate.year += 1
      else:
        pdate.month += 1
    pdate.day += intv - 1
    print(pdate)
    query_db("UPDATE services SET sub_date = ? WHERE user_id = ? AND service_id = ?", (pdate, session["user id"], service[0]))

  elif interval_type == 'weeks':
    intv = pdate.day + interval*7
    while intv > dmax[pdate.month -1]:
      intv -= dmax[pdate.month -1] - pdate.days + 1
      pdate.day = 1
      if pdate.month == 12:
        pdate.month = 1
        pdate.year += 1
      else:
        pdate.month += 1
    pdate.day += intv - 1
    query_db("UPDATE services SET sub_date = ? WHERE user_id = ? AND service_id = ?", (pdate, session["user id"], service[0]))

  elif interval_type == 'months':
    intv = pdate.month + interval
    while intv > 12:
      intv -= 12
      pdate.year += 1
    pdate.month += intv
    query_db("UPDATE services SET sub_date = ? WHERE user_id = ? AND service_id = ?", (pdate, session["user id"], service[0]))

  elif interval_type == 'years':
    pdate.years += interval
    query_db("UPDATE services SET sub_date = ? WHERE user_id = ? AND service_id = ?", (pdate, session["user id"], service[0]))


#session settings
web_site.config["SESSION_FILE_DIR"] = mkdtemp()
web_site.config["SESSION_PERMANENT"] = False
web_site.config["SESSION_TYPE"] = "filesystem"
Session(web_site)

#login required function
# use @login_required
def login_required(f):
  """
  Decorate routes to require login.

  http://flask.pocoo.org/docs/1.0/patterns/viewdecorators/
  """
  @wraps(f)
  def decorated_function(*args, **kwargs):
    if session.get("user_id") is None:
        return redirect("/login")
    return f(*args, **kwargs)
  return decorated_function

#SMS TestPassword
@web_site.route('/send_sms', methods=['POST'])
def send_sms():
  """ A POST endpoint that sends an SMS. """

  # Extract the form values:
  to_number = request.form['to_number']
  message = request.form['message']

  # Send the SMS message:
  client.send_message({
  'from': '15799400707',
  'to': to_number,
  'text': message,
  })

  # Redirect the user back to the form:
  return redirect(url_for('index'))


##fun
@web_site.route('/fun')
@login_required
def fun():
  return render_template("fun.html", loggedin = True)



















@web_site.route('/view_receipts',methods=['GET','POST'])
@login_required
def veiw():
  if request.method == "GET":
    receipts = query_db("SELECT * FROM receipts WHERE user_id=?",[session["user_id"]])
    return render_template("view_receipts.html",receipts=receipts,loggedin=True)
  if request.method == "POST":
    receipt_id=request.form['submit_button']
    print(receipt_id)
    query_db("DELETE FROM receipts WHERE id=?",[receipt_id])
    receipts = query_db("SELECT * FROM receipts WHERE user_id=?",[session["user_id"]])
    return render_template("view_receipts.html",receipts=receipts,loggedin=True)



##receipt-analyzer
@web_site.route('/receipt-analyzer')
@login_required
def receipt_analyzer():
  return render_template("receipt-analyzer.html", loggedin = True)

##compute-receipt-analysis
@web_site.route('/compute-receipt-analysis', methods=['POST'])
def computer_receipt_analysis():
  """ A POST endpoint that applies OCR on a receipt. """

  # Extract the form values:
  img_link= request.form['img_link']
  receipt_name= request.form['unique_name']
  # Do the cool machine learning magic pls.
  # receiptUrl ="https://raw.githubusercontent.com/Azure/azure-sdk-for-python/master/sdk/formrecognizer/azure-ai-formrecognizer/tests/sample_forms/receipt/contoso-receipt.png"

  
  #returns all usernames
  duplicate_checker = query_db("SELECT * FROM receipts WHERE receipt_name=?",[receipt_name])
  #print(existing_users)
  if duplicate_checker:
    flash("You already have a receipt called that! Please try a different name.")
    return render_template("receipt-analyzer.html", loggedin = True)


  receiptUrl = img_link

  poller = form_recognizer_client.begin_recognize_receipts_from_url(receiptUrl)
  result = poller.result()
  the_receipt = {
    "MerchantName": "None",
    "MerchantAddress": "None",
    "MerchantPhoneNumber": "None",
    "TransactionDate": "None",
    "TransactionTime": "None",
    "Subtotal": 0,
    "Tax": 0,
    "Total": 0
  }
  receipt_items = {} 
  for receipt in result:
      for name, field in receipt.fields.items():
          if name == "Items":
              # print("Receipt Items:")
              # for idx, items in enumerate(field.value):
              #     print("...Item #{}".format(idx + 1))
              #     for item_name, item in items.value.items():
              #         print("......{}: {} has confidence {}".format(item_name, item.value, item.confidence))
            for idx, items in enumerate(field.value):
              receipt_items[str(idx+1)]= {}
              for item_name, item in items.value.items():
                receipt_items[str(idx+1)][item_name]= item.value
          else:
            the_receipt[name] = field.value
              # print("{}: {} has confidence {}".format(name, field.value, field.confidence))
  
  print(the_receipt)
  query_db("INSERT INTO receipts (user_id, receipt_name, merchant_name, merchant_address, merchant_phone_number, transaction_date, transaction_time, subtotal, tax, total) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (session["user_id"], str(receipt_name), the_receipt["MerchantName"], the_receipt["MerchantAddress"], str(the_receipt["MerchantPhoneNumber"]), str(the_receipt["TransactionDate"]), str(the_receipt['TransactionTime']), int(the_receipt["Subtotal"]), int(the_receipt["Tax"]), (the_receipt["Total"])))
  
  # print(receipt_items)
  receipt_id = query_db("SELECT * FROM receipts WHERE receipt_name=?",[receipt_name])
  receipt_id = receipt_id[0][0]
  amount_of_items = len(receipt_items)
  magic = 0
  while magic < amount_of_items: 
    num = magic+1
    query_db("INSERT INTO receipt_items (receipt_id, item_number, item_name, item_price) VALUES (?,?,?,?)",(receipt_id, num, str(receipt_items[str(num)]["Name"]), int(receipt_items[str(num)]["TotalPrice"])))
    magic+=1

    
  receipt_id = [0, 1, 2, 3, 4, 5, 6, 7, 8]
  receipt_id[0] = receipt_name
  receipt_id[1] = the_receipt["MerchantName"]
  receipt_id[2] = the_receipt["MerchantAddress"]
  receipt_id[3] = the_receipt["MerchantPhoneNumber"]
  receipt_id[4] = the_receipt["TransactionDate"]
  receipt_id[5] = the_receipt["TransactionTime"]
  receipt_id[6] = the_receipt["Subtotal"]
  receipt_id[7] = the_receipt["Tax"]
  receipt_id[8] = the_receipt["Total"]
  # for k1,v1 in receipt_items.items(): # the basic way
  #   for k2,v2 in v1.items():
  #     # print ( str(k1)+str(k2)+" "+str(v2))
  # Redirect the user back to the form:
  return render_template("receipt_output.html", receipt_id = receipt_id, loggedin = True) 

# query_db("INSERT INTO services (user_id, sub_name, cost, sub_date) VALUES (?, ?, ?, ?)", (session["user_id"], sub_name, cost, sub_date))
# query_db("INSERT INTO users (username,password, phone) VALUES (?,?,?)",(username,generate_password_hash(password),phone))

# existing_users = query_db("SELECT * FROM users WHERE username=?",[username])
#     #print(existing_users)
#     if existing_users:
#       flash("Username already exists. Please try a different username.")
#       return render_template("register.html", loggedin = False, user_count = user_count)















##adding service
@web_site.route('/add_service', methods=["GET", "POST"])
@login_required
def add_service():
  #all services
  service_data = query_db("SELECT * FROM services WHERE user_id=?",[session["user_id"]])
  if request.method == "GET":
    return render_template("add_service.html",services = service_data, loggedin = True)
  if request.method == "POST":
    #form variables
    if request.form["submit_button"] == "add_service":
      sub_name = request.form.get("SubscriptionName")
      cost = request.form.get("Cost")
      sub_date = request.form.get("SubscriptionDate")
      subscriptions = query_db("SELECT sub_name FROM services")

      if not sub_name:
        flash("No Subscription Name Entered. Please Try Again.")
        return render_template("add_service.html", services = service_data, loggedin = True)
      if not cost:
        flash("No Cost Entered. Please Try Again.")
        return render_template("add_service.html", services = service_data, loggedin = True)
      if not sub_date:
        flash("No Subscription Date Entered. Please Try Again.")
        return render_template("add_service.html", services = service_data, loggedin = True)

      #if sub_name in subscriptions:
      #  return render_template("add_service.html", error = "duplicate subscription service")

      query_db("INSERT INTO services (user_id, sub_name, cost, sub_date) VALUES (?, ?, ?, ?)", (session["user_id"], sub_name, cost, sub_date))
      service_data = query_db("SELECT * FROM services WHERE user_id=?",[session["user_id"]])
      flash("Added successfully")
      return render_template("add_service.html", services = service_data, loggedin = True)
    else:
      #all the code for deleting
      sub_id = request.form["submit_button"]
      print(sub_id)
      query_db("DELETE FROM services WHERE service_id = ?",[sub_id])
      service_data = query_db("SELECT * FROM services WHERE user_id=?",[session["user_id"]])
      flash("Deleted successfully")
      return render_template("add_service.html", services = service_data, loggedin = True)

@web_site.route('/download', methods=['GET', 'POST'])
def download():
    # Appending app path to upload folder path within app root folder
    path = "receipts.csv"
    return send_file(path, as_attachment=True)



##main page route
@web_site.route('/', methods=["GET", "POST"])
@login_required
def index():
  if request.method == "GET":

    #format of users database
    #cursor.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT NOT NULL, password TEXT NOT NULL)")
    ##inserting a test user
    #cursor.execute("INSERT INTO users (username,password) VALUES (?,?)",("Sashco","TestPassword"))
    #query_db("CREATE TABLE services (id INTEGER PRIMARY KEY, sub_type TEXT NOT NULL, monthly_cost TEXT NOT NULL, renewal_date TEXT NOT NULL)")
  
    services = query_db("SELECT sub_name, sub_date, cost FROM services WHERE user_id=?",[session["user_id"]])
    
    phone = query_db("SELECT phone FROM users WHERE id=?",[session['user_id']])

    totalcost = 0

    for x in services:
      diff = x[1] - int(date.today().strftime('%d'))
      totalcost+=x[2]
      ##to improve: add column in services table to show if message has been sent already
      if diff <= 7 and diff >= 0:
        client.send_message({
        'from': '15799400707',
        'to': phone,
        'text': 'Your $'+str(x[2])+' per month subscription to '+ str(x[0])+' expires in '+str(diff)+' day(s)',
        })

    #flash('flashing works!')
    print(services)
    return render_template("index.html", services = services, loggedin = True,cost = totalcost)

##login route
@web_site.route('/login', methods=["GET", "POST"])
def login():
  #clear cookies
  session.clear()

  if request.method == "GET":

    #query_db("ALTER TABLE users ADD phone TEXT")
    return render_template("login.html", loggedin = False)
    
  if request.method == "POST":
    username = request.form.get("username")
    password = request.form.get("password")
    #error trap if username/password is blank
    
    if not request.form.get("username"):
      flash('ENTER A USERNAME')
      return render_template("login.html", loggedin = False)
    if not request.form.get("password"):
      flash('ENTER A PASSWORD')
      return render_template("login.html", loggedin = False)

    pwd = query_db("SELECT password FROM users WHERE username = ? ", [username])
    if not pwd:
      flash('No such username exists. Please try again or register a new account.')
      return render_template("login.html", loggedin = False)
    elif not check_password_hash(pwd[0][0], password):
      flash('Incorrect Password. Please try again.')
      return render_template("login.html", loggedin = False)
    else:
      flash('Successful Log In!')
      current_id = query_db("SELECT id FROM users WHERE username=?",[username])
      print(current_id[0][0])
      session["user_id"] = current_id[0][0]
      return redirect("/")

@web_site.route('/logout', methods=["GET", "POST"])
def logout():
  session.clear()
  return redirect("/login")

##register route
@web_site.route('/register', methods=["GET", "POST"])
def register():
  #clear cookies
  session.clear()
  user_count = query_db("SELECT COUNT(username) FROM users")
  if request.method == "GET": ##user views register page
    
    return render_template("register.html", loggedin = False, user_count = user_count)

  if request.method == "POST": ##user attempts to create account
    #returns whatever is inside the username and password fields
    password = request.form.get("password")
    username = request.form.get("username")
    password_confirm = request.form.get("password-confirm")
    phone = request.form.get("phone")

    #returns all usernames
    existing_users = query_db("SELECT * FROM users WHERE username=?",[username])
    #print(existing_users)
    if existing_users:
      flash("Username already exists. Please try a different username.")
      return render_template("register.html", loggedin = False, user_count = user_count)
    #checks if passwords match
    if password != password_confirm:
      flash("Passwords do not match. Please try again.")
      return render_template("register.html", loggedin = False, user_count = user_count)
    #inserts user into user table
    ##change line to insert phone num

    if not phone:
      flash("No phone number entered. Please try again.")
      return render_template("register.html", loggedin = False, user_count = user_count)

    query_db("INSERT INTO users (username,password, phone) VALUES (?,?,?)",(username,generate_password_hash(password),phone))

    current_id = query_db("SELECT id FROM users WHERE username=?",[username])

    #print(current_id[0][0])
    session["user_id"] = current_id[0][0]

    return redirect("/")

##settings page 
@web_site.route('/settings', methods=["GET", "POST"])
@login_required
def settings():
  if request.method =="GET":
    return render_template("settings.html", loggedin = True)
  if request.method=="POST":
    new_number = request.form.get("phone")
    query_db("UPDATE users SET phone=? WHERE id=?", (new_number,session['user_id']))
    flash('Phone number succesfully updated to '+new_number)
    return render_template("settings.html", loggedin = True)


web_site.run(host='0.0.0.0', port=8080)