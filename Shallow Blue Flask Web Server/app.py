# General Library Imports--------------------------------------------------------------------------------------------------
import datetime
import DBInterface
import hashlib
import Ladder_EventClass
import os
import random
import sqlite3
import SR_EventClass
import string
import sys
import WTFClasses

# Specific Imports---------------------------------------------------------------------------------------------------------
from flask import Flask, render_template, redirect, url_for, session, flash
from functools import wraps

# Creating the Flask object------------------------------------------------------------------------------------------------
app = Flask(__name__)

# Adding the app config data
app.config["SECRET_KEY"] = ""
for i in range(0, 10):
    app.config["SECRET_KEY"] += string.printable[random.SystemRandom().randint(0, len(string.printable) - 1)]

# Creating the database object---------------------------------------------------------------------------------------------
rootDirectory = os.path.dirname(__file__)
database = DBInterface.DBInterface(os.path.join(rootDirectory, "Data/DatabaseLocation.txt"), rootDirectory)

# Make the WSGI interface available at the top level so wfastcgi can get it
wsgi_app = app.wsgi_app

# Custom Decorators---------------------------------------------------------------------------------------------------------
def testLogin(func):
    @wraps(func)# Used to preserve the 'signiture' of the function when it is added to app
    def wrapper(*args, **kwargs):
        loggedIn = False

        if "userID" in session:
            loggedIn = True

        return func(loggedIn)

    return wrapper

def forceLogin(func):
    @wraps(func)
    def wrapper(eventID = None, *args, **kwargs):
        if "userID" in session:
            if eventID == None:
                return func()
            else:
                return func(eventID)
        else:
            flash("You must be logged in to view that page.")
            return redirect(url_for("login"))
    return wrapper

# View functions to handele web requests and generate responces-------------------------------------------------------------
@app.route('/')
@app.route('/home')
@testLogin
def home(loggedIn):
    """Splash Page"""
    return render_template("SplashPage.html", loggedIn = loggedIn)

@app.route('/login', methods = ["GET", "POST"])
def login():
    """Login Page"""
    form = WTFClasses.LoginForm()

    if form.validate_on_submit():
        userName = form.usernameTextBox.data
        password = hashlib.sha512(form.passwordPasswordBox.data.encode('utf8')).hexdigest()
        
        userData = database.getUserLogin(userName, password)

        if userData != None:
            session["userID"] = userData[0]
            session["userName"] = userData[1]
            session["firstName"] = userData[2]
            session["lastName"] = userData[3]

            return redirect(url_for("home"))

        else:
            flash("Credentials were incorrect. Please try again.")

    return render_template("LoginPage.html", pageTitle = "Login", form = form)

@app.route('/logout')
@forceLogin
def logout():
    del session["userID"]
    del session["userName"]
    del session["firstName"]
    del session["lastName"]

    flash("You have sucessfully logged out.")

    return redirect(url_for("home"))

@app.route('/signup', methods = ["GET", "POST"])
def signup():
    """Signup Page"""
    form = WTFClasses.SignupForm()

    if form.validate_on_submit():
        year = form.dobYearIntegerBox.data
        month = form.dobMonthIntegerBox.data
        day = form.dobDayIntegerBox.data

        # Validate username and date fields---------------------------------------------------------------------------------
        valid = True

        # Retrive a list of usernames from the database
        userNames = database.getUsernames()

        # Check username is unique
        if form.usernameTextBox.data in userNames:
            form.usernameTextBox.errors.append("This username is allready being used. Please try another")
            valid = False

        try:
            # Check the date is in a sutable range
            datetime.timedelta()
            if datetime.date(year, month, day) > datetime.date.today() or datetime.date(year, month, day) -  datetime.date(1, 1, 1) < datetime.date.today() - datetime.date(120, 1, 1):
                form.dobDayIntegerBox.errors.append("The date provided was not posible as a date of birth. Please try again.")
                valid = False

        except ValueError:
            valid = False

            # Check that day and month values are valid
            if month in [1, 3, 5, 7, 8, 10, 12] and (day < 1 or day > 31):
                form.dobDayIntegerBox.errors.append("The day of the month provided dosen't exist.")

            elif month in [4, 6, 9, 11] and (day < 1 or day > 31):
                form.dobDayIntegerBox.errors.append("The day of the month provided dosen't exist.")
            
            elif month == 2:
                if int(year/4) == int(float(year/4.0)) and (day < 1 or day > 29):
                    form.dobDayIntegerBox.errors.append("The day of the month provided dosen't exist.")

                elif day < 1 or day > 28:
                    form.dobDayIntegerBox.errors.append("The day of the month provided dosen't exist.")

            else:
                form.dobMonthIntegerBox.errors.append("The month provided dosen't exist.")

        # Add the user to the database-------------------------------------------------------------------------------------
        if valid == True:# If the username and date fields are valid
            # In case the username has been taken by another user after the check
            try:
                database.addUser(form.usernameTextBox.data, form.firstNameTextBox.data, form.lastNameTextBox.data, hashlib.sha512(form.passwordPasswordBox.data.encode('utf8')).hexdigest(), form.emailTextBox.data, datetime.datetime(year, month, day).timestamp())

            except sqlite3.IntegrityError:
                 form.usernameTextBox.errors.append("This username is allready being used. Please try another")

                 return render_template("SignupPage.html", pageTitle = "Signup", form = form)

            # Log the new user in
            userData = database.getUserLogin(form.usernameTextBox.data, hashlib.sha512(form.passwordPasswordBox.data.encode('utf8')).hexdigest())

            session["userID"] = userData[0]
            session["userName"] = userData[1]
            session["firstName"] = userData[2]
            session["lastName"] = userData[3]

            flash("Welcome %s." %(form.usernameTextBox.data))

            return redirect(url_for("home"))

    return render_template("SignupPage.html", pageTitle = "Signup", form = form)

@app.route('/profile')
@forceLogin
def profile():
    userData = []
    
    for item in database.getUser(session["userName"]):
        userData.append(item)

    userData.pop(4)

    if userData[5] != None:
        userData[5] = datetime.datetime.fromtimestamp(int(userData[5]))
        userData[5] = userData[5].strftime(format = "%d/%m/%Y")

    return render_template("ProfilePage.html", pageTitle = "Profile", user = userData)

@app.route('/watch')
def spectate():
    """Spectate Page"""
    events = database.getEventListings()

    listings = []

    for event in events:
        if event[4] != "finished":
            listings.append([event[0], event[1], datetime.datetime.fromtimestamp(int(event[2])), event[3]])

    listings.sort(key = lambda event: event[2])

    return render_template("JoinPage.html", pageTitle = "Spectate", eventData = listings)

@app.route('/join', methods = ["GET", "POST"])
@forceLogin
def join():
    """Join Page"""
    form = WTFClasses.CreateEvent()

    if form.validate_on_submit():
        name = form.eventNameTextBox.data
        info = form.infoTextBox.data
        eventType = form.typeSelector.data
        year = form.startYearIntegerBox.data
        month = form.startMonthIntegerBox.data
        day = form.startDayIntegerBox.data
        hour = form.startHourIntegerBox.data
        minute = form.startMinuteIntegerBox.data
        winScore = form.winScoreFloatBox.data
        drawScore = form.drawScoreFloatBox.data
        loseScore = form.loseScoreFloatBox.data
        noShowScore = form.noShowScoreFloatBox.data

        noRounds = form.maxRoundsIntegerBox.data
        noPlayers = form.playersIntegerBox.data

        valid = True

        try:
            winScore = float(winScore)
        except ValueError as e:
            form.winScoreFloatBox.errors.append("This field must contain a valid decimal or integer.")
            valid = False

        try:
            drawScore = float(drawScore)
        except ValueError as e:
            form.drawScoreFloatBox.errors.append("This field must contain a valid decimal or integer.")
            valid = False

        try:
            loseScore = float(loseScore)
        except ValueError as e:
            form.drawScoreFloatBox.errors.append("This field must contain a valid decimal or integer.")
            valid = False

        try:
            noShowScore = float(noShowScore)
        except ValueError as e:
            form.drawScoreFloatBox.errors.append("This field must contain a valid decimal or integer.")
            valid = False

        try:
            # Check the date is in a sutable range
            datetime.timedelta()
            if datetime.datetime(year, month, day, hour, minute) < datetime.datetime.now():
                form.dobDayIntegerBox.errors.append("The date provided was not posible as a date of birth. Please try again.")
                valid = False

        except ValueError:
            valid = False

            # Check that day and month values are valid
            if month in [1, 3, 5, 7, 8, 10, 12] and (day < 1 or day > 31):
                form.dobDayIntegerBox.errors.append("The day of the month provided doesn't exist.")

            elif month in [4, 6, 9, 11] and (day < 1 or day > 31):
                form.dobDayIntegerBox.errors.append("The day of the month provided doesn't exist.")
            
            elif month == 2:
                if int(year/4) == int(float(year/4.0)) and (day < 1 or day > 29):
                    form.dobDayIntegerBox.errors.append("The day of the month provided doesn't exist.")

                elif day < 1 or day > 28:
                    form.dobDayIntegerBox.errors.append("The day of the month provided doesn't exist.")

            if hour > 23 or hour < 0:
                form.startHourIntegerBox.errors.append("The hour provided doesn't exist.")

            if minute > 59 or minute < 0:
                form.startMinuteIntegerBox.errors.append("The minute provided doesn't exist.")

            else:
                form.dobMonthIntegerBox.errors.append("The month provided doesn't exist.")

        if winScore < 0:
            form.winScoreFloatBox.errors.append("The win score must be positive.")
            valid = False

        if winScore <= loseScore:
            form.winScoreFloatBox.errors.append("The win score must be larger than the lose score.")
            valid = False

        if valid:
            if eventType == "ladder":
                if noPlayers != None and noPlayers < 6:
                    valid = False
                    flash("You need to expect more than five players to run a ladder event. If you wish to continue, clear the 'Estimated Players' field.")

                noRounds = 0

            elif eventType == "round robin":
                if noPlayers != None and noPlayers > 8:
                    valid = False
                    flash("It is unrealistic to run a round robin event with more than 8 players. If you wish to continue, clear the 'Estimated Players' field.")

                if noPlayers != None and noRounds != None and noRounds < noPlayers - 1:
                    valid = False
                    flash("You have specified a round robin event with approximatly " + str(noPlayers) + " players. This will take a minimum of " + str(noPlayers - 1) + " rounds to complete. If you wish to continue, clear the 'Number of Rounds' field.")

            else:# swiss
                if noRounds != None and noRounds < 5:
                    valid = False
                    flash("You need to expect at least five rounds to run a swiss event. If you wish to continue, clear the 'Number of Rounds' field.")

            if valid == True:
                admin = database.getUserLogin("admin", hashlib.sha512(form.adminPasswordBox.data.encode('utf8')).hexdigest())

                if admin != None:
                    database.addEvent(name, info, session["userID"], eventType, datetime.datetime(year, month, day, hour, minute).timestamp(), noRounds, winScore, drawScore, loseScore, noShowScore)
                    flash("The event " + name + " has sucessfully been created. To join the event, select it from 'Join'. To administer the event, access it through 'Spectate'.")
                    return redirect(url_for("home"))
                else:
                    flash("The admin password was either wrong or wasn't entered. Please ask the admin to enter their password to create the event.")

    events = database.getEventListings()

    listings = []

    for event in events:
        if event[4] == "registration" and datetime.datetime.fromtimestamp(int(event[2])) > datetime.datetime.now() or event[5] == "ladder" and event[4] != "finished":
            listings.append([event[0], event[1], datetime.datetime.fromtimestamp(int(event[2])), event[3]])

    listings.sort(key = lambda event: event[2])

    return render_template("JoinPage.html", pageTitle = "Join", eventData = listings, form = form)

@app.route('/<eventID>/join')
@forceLogin
def joinEvent(eventID):
    event = None

    #Create the event object
    eventData = database.getEvent(eventID)

    if eventData != None:
        if eventData[4] == "ladder":
            event = Ladder_EventClass.Ladder_Event(database, eventData)
        else:
            event = SR_EventClass.SR_Event(database, eventData)

    try:
        event.addPlayer(database, session["userID"])

    except:
        flash("You have allready joined this event. You can only join an event once.")

    return redirect(url_for("homepage", eventID = eventID))

@app.route('/<eventID>/home')
def homepage(eventID):
    event = None

    #Create the event object
    eventData = database.getEvent(eventID)

    if eventData != None:
        if eventData[4] == "ladder":
            event = Ladder_EventClass.Ladder_Event(database, eventData)
        else:
            event = SR_EventClass.SR_Event(database, eventData)

        return render_template("EventHomePage.html", event = event, pageTitle = "Home", homeClass = "active", session = session)

    else:
        flash("You tried to access an event that doesn’t exist.")
        return redirect(url_for("home"))

@app.route('/<eventID>/addPlayer', methods = ["GET", "POST"])
@forceLogin
def addPlayer(eventID):
    event = None

    #Create the event object
    eventData = database.getEvent(eventID)
    if eventData[4] == "ladder":
        event = Ladder_EventClass.Ladder_Event(database, eventData)
    else:
        event = SR_EventClass.SR_Event(database, eventData)

    if session["userID"] != event.creatorID:
        flash("You don't have permission to access that page.")
        return redirect(url_for("homepage", eventID = eventID))

    form = WTFClasses.AddPlayer()

    if form.validate_on_submit():
        name = form.usernameTextBox.data + " : " + str(datetime.datetime.now())

        database.addNoUserPlayer(name)

        event.addPlayer(database, database.getUser(name)[0])

        flash("The user " + name + "has been added.")

        return redirect(url_for("scores", eventID = eventID))

    return render_template("AddPlayerPage.html", event = event, form = form, pageTitle = "Add Player", addPlayerClass = "active", session = session)

@app.route('/<eventID>/pairings', methods = ["GET", "POST"])
def pairings(eventID):
    event = None

    #Create the event object
    eventData = database.getEvent(eventID)
    if eventData[4] == "ladder":
        event = Ladder_EventClass.Ladder_Event(database, eventData)
    else:
        event = SR_EventClass.SR_Event(database, eventData)

    currentPairings = event.getPairings(database)

    returnForm = WTFClasses.ResultForm()

    if returnForm.validate_on_submit():
        pairingNumber = int(returnForm.pairingIdentifier.data)
        matchNumber = int(returnForm.matchNumber.data)
        valid = False

        if returnForm.blackResultSelector.data == "W":
            if returnForm.whiteResultSelector.data in ["L", "NS"]:
                valid = True
        elif returnForm.blackResultSelector.data == "D":
            if returnForm.whiteResultSelector.data == "D":
                valid = True
        elif returnForm.blackResultSelector.data == "L":
            if returnForm.whiteResultSelector.data == "W":
                valid = True
        elif returnForm.blackResultSelector.data == "NS":
            if returnForm.whiteResultSelector.data in ["W", "NS"]:
                valid = True

        if valid == True:
            status = event.updatePairing(database, matchNumber, event.getPlayer(currentPairings[pairingNumber][1]), returnForm.blackResultSelector.data, event.getPlayer(currentPairings[pairingNumber][2]), returnForm.whiteResultSelector.data)
            if status == "End of event":
                return redirect(url_for("homepage", eventID = eventID))
            elif status == "End of round":
                return render_template("PairingsPage.html", event = event, startNextRound = True, pageTitle = "Pairings", pairings = [], forms = [], pairingsClass = "active", session = session)
            else:
                return redirect(url_for("pairings", eventID = eventID))
                
    currentPairings = event.getPairings(database)

    forms = []

    for pairingNumber in range(0, len(currentPairings)):
        if currentPairings[pairingNumber][8] == None:
            forms.append(WTFClasses.ResultForm())
            forms[len(forms) - 1].pairingIdentifier.data = str(pairingNumber)
            forms[len(forms) - 1].matchNumber.data = str(currentPairings[pairingNumber][0])
            forms[len(forms) - 1].blackResultSelector.data = ""
            forms[len(forms) - 1].whiteResultSelector.data = ""

    if len(forms) == 0 and event.eventType != "ladder":
        return render_template("PairingsPage.html", event = event, startNextRound = True, pageTitle = "Pairings", pairings = [], forms = [], pairingsClass = "active", session = session)
    else:
        return render_template("PairingsPage.html", event = event, startNextRound = False, pageTitle = "Pairings", pairings = currentPairings, forms = forms, pairingsClass = "active", session = session)

@app.route('/<eventID>/startRound')
@forceLogin
def startRound(eventID):
    event = None

    #Create the event object
    eventData = database.getEvent(eventID)
    if eventData[4] == "ladder":
        flash("That event type can't have pairings generated for it.")
        return redirect(url_for("home"))
    event = SR_EventClass.SR_Event(database, eventData)

    if session["userID"] != event.creatorID:
        flash("You don't have permission to access that page.")
        return redirect(url_for("homepage", eventID = eventID))

    if event.round == 0:
        if len(event.players) < 2:
            flash("You can't start a " + event.eventType + " event with fewer than two players.")
            return redirect(url_for("pairings", eventID = eventID))
        event.startEvent(database)

    event.createPairings(database)

    return redirect(url_for("pairings", eventID = eventID))

@app.route('/<eventID>/startLadderEvent')
@forceLogin
def startLadderEvent(eventID):
    event = None

    #Create the event object
    eventData = database.getEvent(eventID)
    if eventData[4] == "ladder":
       event = Ladder_EventClass.Ladder_Event(database, eventData)
    else:
        flash("Only ladder events can be started in this way.")
        return redirect(url_for("home"))

    if session["userID"] != event.creatorID:
        flash("You don't have permission to access that page.")
        return redirect(url_for("homepage", eventID = eventID))
    
    event.startEvent(database)
    
    return redirect(url_for("pairings", eventID = eventID))

@app.route('/<eventID>/addPairings', methods = ["GET", "POST"])
@forceLogin
def addLadderPairings(eventID):
    event = None

    #Create the event object
    eventData = database.getEvent(eventID)
    if eventData[4] == "ladder":
        event = Ladder_EventClass.Ladder_Event(database, eventData)
    else:
        flash("That event type can't have manual pairings.")
        return redirect(url_for("home"))

    if session["userID"] != event.creatorID:
        flash("You don't have permission to access that page.")
        return redirect(url_for("homepage", eventID = eventID))

    form = WTFClasses.PairingForm()

    formPlayers = [[0, ""]]

    for player in event.players:
        formPlayers.append([player.id, player.name])

    form.blackNameSelector.choices = formPlayers
    form.whiteNameSelector.choices = formPlayers

    if form.validate_on_submit():
        valid = True

        if form.blackNameSelector.data == form.whiteNameSelector.data:
            valid = False
            form.blackNameSelector.errors.append("Two different players must be selected.")

        bPlayer = event.getPlayer(int(form.blackNameSelector.data))
        wPlayer = event.getPlayer(int(form.whiteNameSelector.data))

        if bPlayer.position + 2 < wPlayer.position or wPlayer.position + 2 < bPlayer.position:
            valid = False
            form.blackNameSelector.errors.append("The specified players are too far appart. They should be at most one player between them.")

        if valid == True:
            try:
                event.addPairing(database, bPlayer, wPlayer)

                return redirect(url_for("pairings", eventID = eventID))
            except ValueError as e:
                form.blackNameSelector.errors.append(e.args[0])

    form.blackNameSelector.data = ""
    form.whiteNameSelector.data = ""
    
    return render_template("AddPairingsPage.html", pageTitle = "Add Pairing", event = event, form = form, pairingsClass = "active")

@app.route('/<eventID>/scores')
def scores(eventID):
    event = None

    #Create the event object
    eventData = database.getEvent(eventID)
    if eventData[4] == "ladder":
        event = Ladder_EventClass.Ladder_Event(database, eventData)
    else:
        event = SR_EventClass.SR_Event(database, eventData)

    event.players.sort(key = lambda player: player.position)

    return render_template("ScoresPage.html", pageTitle = "Scores and Progress", event = event, progressClass = "active", session = session)

if __name__ == '__main__':
    # Runs the web server using the IPv4 adress passed in as an argument
    app.run(str(sys.argv[1]), 5555, threaded = True)
    # Visual Studio Code For Debugging-------------------------------------------------------------------------------------
    #TODO: Comment out this section before relice
    #import os
    #HOST = os.environ.get('SERVER_HOST', 'localhost')
    #try:
    #    PORT = int(os.environ.get('SERVER_PORT', '5555'))
    #except ValueError:
    #    PORT = 5555
    # Run the web server---------------------------------------------------------------------------------------------------
    #app.run(HOST, PORT, threaded = True)