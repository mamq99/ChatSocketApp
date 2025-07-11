import socket
import threading
import time
import select
import sys

class ChatServer:
    def __init__(self, host='', port=50007):
        self.HOST = host
        self.PORT = port
        self.MSG_BYTES = 2048
        self.clients = {}  # {socket: username}
        self.timeoutDuration = 10
        self.threadTimeout = 3.0
        self.client_backlog_queue = 5
        self.server_running = threading.Event()
        self.server_running.set()
        self.lock = threading.Lock()
        self.message_threads = []
        self.sock = None
        self.monitorThread = None
        self.adminThread = None

    def admin_commands(self):
        """Handle admin commands from console input"""
        while self.server_running.is_set():
            try:
                if sys.stdin.closed:
                    break
                cmd = input()
                if cmd.strip().lower() == "!exitserver":
                    print("Manual shutdown of server commenced.")
                    
                    # Clear the event first to signal all threads to stop
                    self.server_running.clear()
                    
                    # Send shutdown message to clients
                    self.broadcast("!server_shutdown".encode(), None)

                    # Give threads a moment to process the shutdown signal
                    time.sleep(0.5)

                    with self.lock:
                        for client in list(self.clients.keys()):
                            print(f"Removing client | alive: {client.fileno() != -1}")
                            try:
                                client.shutdown(socket.SHUT_RDWR)
                            except Exception as e:
                                print(f"ADMIN_COMMAND: client shutdown error: {e}")
                            try:
                                client.close()
                                print(f"ADMIN_COMMAND: Client close: {client}")
                            except Exception as e:
                                print(f"ADMIN_COMMAND: Error client close: {e}")
                            self.close_client_socket(client, "ADMIN")
            except EOFError:
                self.server_running.clear()
                break
            except Exception as e:
                print(f"ADMIN_COMMAND: Unexpected error: {e}")
                self.server_running.clear()
                break

    def set_username(self, client, address):
        """Set username for a new client connection"""
        try:
            rlist, _, _ = select.select([client], [], [], self.timeoutDuration)
            if not rlist:
                print(f"No data from {address} in time.")
                client.close()
                return None

            username = client.recv(self.MSG_BYTES)
            if not username:
                print(f"SET_USERNAME: Empty data received from {address}")
                client.close()
                return None
            
            decoded = username.decode()
            if decoded.startswith("JOIN:"):
                username = decoded[5:].strip()
                if not username:
                    client.send("SET_USERNAME: Username cannot be empty.".encode())
                    client.close()
                    return None
                
                with self.lock:
                    self.clients[client] = username
                print(f"Username {username} joined the chat from {address}")
                self.broadcast(f"{username} has joined the chat.".encode(), None)
                return username
            else:
                client.send("SET_USERNAME: Invalid Protocol. Use JOIN <username>".encode())
                client.close()
                return None
        except Exception as e:
            print(f"SET_USERNAME: Error receiving username from {address}: {e}")
            client.close()
            return None

    def monitor_server(self, serv_socket, timeoutDuration):
        """Monitor server for auto-shutdown when no clients"""
        empty_since = None

        while self.server_running.is_set():
            time.sleep(1)
            with self.lock:
                active_clients = len(self.clients)

            if active_clients == 0:
                if empty_since is None:
                    empty_since = time.time()
                elif time.time() - empty_since >= timeoutDuration:
                    print(f"No clients for {timeoutDuration} seconds. Closing server...")
                    serv_socket.close()
                    self.server_running.clear()
                    print("MONITOR_SERVER: Server closed.")
                    break
            else:
                empty_since = None

    def authenicate_and_register(self, client, addr):
        username = self.set_username(client, addr)

        if not username:
            print(f"[DEBUG] Username not set for {addr}. Client may have disconnected early.")
            self.close_client_socket(client, context="HANDLE_USERNAME", address=addr)
            return
        print(f"[DEBUG] Entering the message loop for {username}@{addr}")
        return username
    
    def handle_messages(self, client, username, addr):
        while self.server_running.is_set():
                try:
                    client.settimeout(1.0)
                    msg = client.recv(self.MSG_BYTES)

                    if not msg:
                        print(f"[DISCONNECT] {username}@{addr} sent empty data or disconnected.")
                        self.broadcast(f"{username} left the chat.".encode(), None)
                        break

                    decoded = msg.decode(errors="ignore").strip()
                    if decoded == "!quit":
                        print(f"[QUIT] {username}@{addr} requested to quit.")
                        self.broadcast(f"{username} left the chat.".encode(), None)
                        self.remove_client(client, "Quit Chat", graceful=True)
                        break
                    else:
                        formatted_msg = f"{username}: {decoded}"
                        self.broadcast(formatted_msg.encode(), client)

                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"[ERROR] Inner recv loop error for {username}@{addr}: {e}")
                    break

    def cleanup_client(self, client, username, addr):
        with self.lock:
                if client in self.clients:
                    print(f"[CLEANUP] Removing client | alive: {client.fileno() != -1}")
                    removed_user = self.clients[client]
                    print(f"[CLEANUP] {removed_user} removed from chat.")
                    del self.clients[client]

                    if self.server_running.is_set():
                        self.broadcast(f"{removed_user} removed from the chat.".encode(), None)
                        
        self.close_client_socket(client, context="HANDLE_CLIENT", address=addr, user=username)


    def handle_client(self, client, addr):
        print(f"[CONNECT] Connected to: {addr}")

        username = self.authenicate_and_register(client, addr)
        if not username:
            return
        
        try:
            self.handle_messages(client, username, addr)
        except Exception as outer_e:
            print(f"[ERROR] Outer exception for {username}@{addr}: {outer_e}")
        finally:
            self.cleanup_client
            
            

    def broadcast(self, message, sender):
        """Broadcast message to all clients except sender"""

        dead_clients = []
        if not self.server_running.is_set():
            return #skip broadcast during shutdown
        
        with self.lock:
            client_list = list(self.clients.keys())

        for client in client_list:
            if client != sender:
                try:
                    client.settimeout(1.0) #prevents indefinite block
                    client.send(message)
                    print(f"BROADCAST: {message.decode()}")
                except Exception as e:
                    # Newly added
                    username = self.clients.get(client, "Unknown")
                    print(f"BROADCAST: {e} - could not send to {username}")
                    dead_clients.append(client)
        if dead_clients:
            for dead in dead_clients:
                self.remove_client(dead, "Broadcast_Failure", graceful=False)

    def remove_client(self, client, reason="", graceful=False):
        """Safely remove an unreachable client from the server"""
        with self.lock:
            username = self.clients.get(client, "Unknown")
            if client in self.clients:
                if not graceful:
                    print(f"[CLEANUP] Removing unreachable client: {username} | Reason: {reason}")
                del self.clients[client]

        # Inform others only if the server is still running
        if self.server_running.is_set() and not graceful:
            self.broadcast(f"{username} has disconnected unexpectedly.".encode(), None)

        self.close_client_socket(client,context="REMOVE_DEAD_CLIENT", user=username)
                    

    def start(self):
        """Start the chat server"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as self.sock:
            self.sock.bind((self.HOST, self.PORT))
            self.sock.listen(self.client_backlog_queue)
            print("Server is listening...")

            self.monitorThread = threading.Thread(target=self.monitor_server, args=(self.sock, self.timeoutDuration), daemon=False)
            self.adminThread = threading.Thread(target=self.admin_commands, daemon=True)

            self.monitorThread.start()
            self.adminThread.start()

            self.sock.settimeout(1.0)
            while self.server_running.is_set():
                try:
                    client, addr = self.sock.accept()
                    t = threading.Thread(target=self.handle_client, args=(client, addr))
                    t.start()

                    # Track the thread
                    self.message_threads.append(t)

                    # Cleanup finished threads periodically
                    self.message_threads = [th for th in self.message_threads if th.is_alive()]

                except socket.timeout:
                    continue
                except OSError as e:
                    if self.server_running.is_set():
                        print(f"MAIN: Server accept failed: {e}")
                    break
                except Exception as e:
                    if self.server_running.is_set():
                        print(f"MAIN: Unexpected error: {e}")
                    break

            self.server_cleanup()

    def close_client_socket(self, client, context="", address=None, user=None):
        if address:
            print(f"[CLOSE] Closing socket for address: {address}")
        if user:
            print(f"[CLOSE] Cleanup for user: {user}")

        try:
            client.shutdown(socket.SHUT_RDWR)
        except Exception as e:
            if context:
                print(f"[{context}] Error shutting down socket: {e}")

        try:
            client.close()
            if context:
                print(f"[{context}] Socket closed successfully.")
        except Exception as e:
            if context:
                print(f"[{context}] Error closing socket: {e}")


    

    def server_cleanup(self):
        """Clean up threads and resources"""
        print("Waiting for client threads to finish...")
        # Wait for threads with a timeout to prevent hanging
        for t in self.message_threads:
            t.join(timeout=self.threadTimeout)
            if t.is_alive():
                print(f"Warning: Thread {t} did not finish within timeout")

        # Wait for daemon threads to finish
        print("Waiting for daemon threads to finish...")
        if self.monitorThread:
            self.monitorThread.join(timeout=2.0)
        
        # Skipped adminThread.join() to avoid blocking on stdin

        # if self.adminThread:
        #     self.adminThread.join(timeout=2.0)
        
        ### COMMENTED BECAUSE NOT DOING adminThread.Join()

        # if self.monitorThread and self.monitorThread.is_alive():
        #     print("Warning: Monitor thread did not finish within timeout")
        # if self.adminThread and self.adminThread.is_alive():
        #     print("Warning: Admin thread did not finish within timeout")

        print("Server shutdown complete.")

def main():
    """Main function to start the chat server"""
    server = ChatServer()
    server.start()

if __name__ == "__main__":
    main()