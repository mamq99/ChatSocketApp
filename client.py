import socket
import threading
import sys
from prompt_toolkit import PromptSession, prompt
from prompt_toolkit.patch_stdout import patch_stdout

HOST = '127.0.0.1'
PORT = 5007
MSG_BYTES = 2048

class ChatClient:
    def __init__(self):
        self.running = threading.Event()
        self.running.set()
        self.sock = None

    def get_username(self, sock):
        username = prompt("Enter Your Username: ").strip()
        sock.send(f"JOIN:{username}".encode())

    def send_message(self, send_sock):
        session = PromptSession()
        with patch_stdout():
            while self.running.is_set():
                    try:
                        if not self.running.is_set():
                            break
                        input_message = session.prompt("You:").strip()
                        if not self.running.is_set():
                            break
                        send_sock.send(input_message.encode())
                        if input_message.strip() == "!quit":
                            self.running.clear()  # Signal this client's threads to stop
                            try:
                                send_sock.shutdown(socket.SHUT_RDWR)
                                send_sock.close()
                            except OSError:
                                pass
                            break
                    except OSError as e:
                        print(f"Send error: {e}")
                        self.running.clear()
                        break    

    def receive_message(self, receive_sock):
        while self.running.is_set():
            try:
                if self.running.is_set():
                    message = receive_sock.recv(MSG_BYTES)
                if not message or not self.running.is_set(): 
                    print("Server disconnected.")
                    self.running.clear()
                    break
                decoded_message = message.decode()
                if decoded_message == "!server_shutdown":
                    self.running.clear()
                    print("Server has closed the connection.")
                    break
                sys.stdout.write(f"\r{decoded_message}\n")
            except OSError as e:
                if not self.running.is_set():
                    break # Suppress error if quitting intentionally by typing "!quit"
                print(f"RECEIVE_M: Receive error: {e}")
                self.running.clear()
                break


def main():
    client = ChatClient()
    client.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.sock.connect((HOST, PORT))
    client.get_username(client.sock)

    receiveMessageThread = threading.Thread(target=client.receive_message, args=(client.sock,))
    sendMessageThread = threading.Thread(target=client.send_message, args=(client.sock,))

    receiveMessageThread.start()
    sendMessageThread.start()

    # Wait for both threads to finish
    sendMessageThread.join()
    receiveMessageThread.join()

    # Clean up socket
    try:
        client.sock.close()
    except:
        pass

    print("Client disconnected.")

if __name__ == "__main__":
    main()
