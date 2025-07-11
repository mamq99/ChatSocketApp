---
title: Chat Socket App (CLI)
---

A simple command-line based two-way chat application built using
Python\'s socket library. This project features a TCP-based
client-server architecture that supports real-time messaging across
multiple clients.\
\
It is ideal for learning how low-level socket communication and
multi-threaded server handling work in Python. This tool runs entirely
from the command line and does not require any GUI or external database.

# NOTE
This is not the final version of this App. This is the first properly working
version. It currently only supports broadcast messaging only. Further details 
of the features is given below. More features coming soon... \

# 🚀 Features

\- Real-time messaging between multiple clients.\
- Supports !quit (client-side) and !exitserver (admin/server-side)
commands.\
- Auto-shutdown feature: the server shuts down after all clients leave
and a timeout passes.\
- Thread-safe handling of client connections.\
- Graceful handling of disconnections and crashes.\
- Built-in admin interface through console input.

# ▶️ How to Run

## 1. Start the server

\`\`\`bash\
python server.py\
\`\`\`

The server will start listening on the default port 50007 and wait for
incoming client connections.\
\
You can shut it down manually anytime using:

\`\`\`bash\
!exitserver\
\`\`\`

## 2. Connect a client

Open another terminal and run:

\`\`\`bash\
python client.py\
\`\`\`

You will be prompted to enter a username. The client then connects to
the server and joins the chatroom.\
\
Multiple clients can be launched from different terminals or machines
connected on the same local network.

# 🧠 How It Works

## 📁 server.py

\- Starts a TCP socket server that listens for client connections.\
- Each client is handled in its own thread.\
- Maintains a dictionary of connected clients and their usernames.\
- Manages user join/leave announcements and message broadcasting.\
- Includes a background monitor thread that shuts down the server if no
clients are connected for a period of time.\
- Also includes an admin thread that listens for server commands from
the console (!exitserver).\
- Threads are joined safely during shutdown to avoid hanging, except for
the admin thread which is skipped to avoid blocking on input().

## 📁 client.py

\- Connects to the server and sends the chosen username.\
- Continuously listens for server messages and prints them.\
- Reads user input and sends it to the server.\
- Gracefully exits using the !quit command or automatically on Ctrl+C.

# 🔁 Code Flow (Server Side)

1\. Main Function → Starts ChatServer and calls .start().\

2. start() → Begins listening on a socket, spawns:\
- A monitor thread to detect idleness and shut down the server.\
- An admin thread to accept server-side input.\

3. New Client Connects → A new thread runs handle_client():\
- Calls set_username() to get and store the username.\
- Starts a loop in handle_messages() to receive and broadcast messages.\
- If the client sends !quit, it triggers remove_client().\

4. Client Disconnects → The client is removed from the shared
dictionary.\

5. No Clients Left → Monitor thread waits a specified timeout (e.g., 10
seconds), then shuts down the server gracefully.

# 📎 Protocol Design

\- On connect, client must send:\
JOIN:\<username\>\
\
- To leave:\
!quit\
\
- Server commands:\
!exitserver (typed into the server terminal)\
\
- System messages and broadcasts are automatically handled by the
server.

# 🛠 Requirements

\- Python 3.6 or higher\
- prompt_toolkit 3.0.51 Needed
- No Other libraries needed (built on Python's standard library)

# 📌 Notes

\- This app is best tested locally or on a shared Wi-Fi.\
- To allow multiple machines to connect, replace localhost in client.py
with the server\'s IP address.\
- Firewalls or antivirus software may need to allow Python to
communicate over the network.

# 🤝 Contributing

Pull requests are welcome. Feel free to fork this project and enhance
the protocol, add logging, or even extend it with encryption or GUI
support.

# 📜 License

This project is open source and available under the MIT License.
