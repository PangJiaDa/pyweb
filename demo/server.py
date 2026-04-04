# @pyweb:start id="0e6262b0" name="Root"
# @pyweb:start id="3ee86cb7" name="Comments"
"""A simple HTTP API server for a todo list."""
# @pyweb:end id="3ee86cb7"
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any


# @pyweb:start id="3d3d7f1e" name="persistence"
# @pyweb:prose some random scrap ass prose comments. \n\n\n hehe
@dataclass
class Todo:
    id: int
    title: str
    done: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    tags: list[str] = field(default_factory=list)
    priority: int = 0


class TodoStore:
    def __init__(self) -> None:
        self._todos: dict[int, Todo] = {}
        self._next_id: int = 1

    def add(self, title: str, tags: list[str] | None = None, priority: int = 0) -> Todo:
        todo = Todo(
            id=self._next_id,
            title=title,
            tags=tags or [],
            priority=priority,
        )
        self._todos[todo.id] = todo
        self._next_id += 1
        return todo

    def get(self, todo_id: int) -> Todo | None:
        return self._todos.get(todo_id)

    def list_all(self, include_done: bool = True) -> list[Todo]:
        todos = list(self._todos.values())
        if not include_done:
            todos = [t for t in todos if not t.done]
        return sorted(todos, key=lambda t: (-t.priority, t.created_at))

    def toggle(self, todo_id: int) -> Todo | None:
        todo = self._todos.get(todo_id)
        if todo:
            todo.done = not todo.done
        return todo

    def delete(self, todo_id: int) -> bool:
        if todo_id in self._todos:
            del self._todos[todo_id]
            return True
        return False

    def search(self, query: str) -> list[Todo]:
        query = query.lower()
        return [
            t for t in self._todos.values()
            if query in t.title.lower() or any(query in tag.lower() for tag in t.tags)
        ]

    def stats(self) -> dict[str, Any]:
        all_todos = list(self._todos.values())
        done = [t for t in all_todos if t.done]
        tag_counts: dict[str, int] = {}
        for t in all_todos:
            for tag in t.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        return {
            "total": len(all_todos),
            "done": len(done),
            "pending": len(all_todos) - len(done),
            "completion_rate": round(len(done) / len(all_todos) * 100, 1) if all_todos else 0,
            "top_tags": sorted(tag_counts.items(), key=lambda x: -x[1])[:5],
        }


store = TodoStore()

# Seed with some data
store.add("Set up CI/CD pipeline", tags=["devops", "infra"], priority=3)
store.add("Write unit tests for auth module", tags=["testing", "auth"], priority=2)
store.add("Review PR #42", tags=["review"], priority=1)
store.add("Update README with API docs", tags=["docs"], priority=1)
store.add("Fix timezone bug in scheduler", tags=["bug", "scheduler"], priority=3)

# @pyweb:end id="3d3d7f1e"


# @pyweb:start id="d89d3b92" name="handler"

class RequestHandler(BaseHTTPRequestHandler):
    # @pyweb:start id="cdb09dda" name="cool bean"
    def do_GET(self) -> None:
        if self.path == "/todos":
            self.handle_list_todos()
        elif self.path.startswith("/todos/search?q="):
            query = self.path.split("q=", 1)[1]
            self.handle_search(query)
        elif self.path == "/todos/stats":
            self.handle_stats()
        elif self.path.startswith("/todos/"):
            try:
                todo_id = int(self.path.split("/")[-1])
                self.handle_get_todo(todo_id)
            except ValueError:
                self.send_error_response(400, "Invalid todo ID")
        else:
            self.send_error_response(404, "Not found")

    def do_POST(self) -> None:
        if self.path == "/todos":
            self.handle_create_todo()
        elif self.path.startswith("/todos/") and self.path.endswith("/toggle"):
            try:
                todo_id = int(self.path.split("/")[-2])
                self.handle_toggle(todo_id)
            except ValueError:
                self.send_error_response(400, "Invalid todo ID")
        else:
            self.send_error_response(404, "Not found")

    def do_DELETE(self) -> None:
        if self.path.startswith("/todos/"):
            try:
                todo_id = int(self.path.split("/")[-1])
                self.handle_delete(todo_id)
            except ValueError:
                self.send_error_response(400, "Invalid todo ID")
        else:
            self.send_error_response(404, "Not found")
    # @pyweb:end id="cdb09dda"

    # @pyweb:start id="1966fb8d" name="handlers"
    def handle_list_todos(self) -> None:
        todos = store.list_all()
        self.send_json_response(200, [asdict(t) for t in todos])

    def handle_get_todo(self, todo_id: int) -> None:
        todo = store.get(todo_id)
        if todo:
            self.send_json_response(200, asdict(todo))
        else:
            self.send_error_response(404, f"Todo {todo_id} not found")

    def handle_search(self, query: str) -> None:
        results = store.search(query)
        self.send_json_response(200, [asdict(t) for t in results])

    def handle_stats(self) -> None:
        self.send_json_response(200, store.stats())

    def handle_create_todo(self) -> None:
        body = self.read_body()
        if not body or "title" not in body:
            self.send_error_response(400, "Missing 'title' field")
            return
        todo = store.add(
            title=body["title"],
            tags=body.get("tags", []),
            priority=body.get("priority", 0),
        )
        self.send_json_response(201, asdict(todo))

    def handle_toggle(self, todo_id: int) -> None:
        todo = store.toggle(todo_id)
        if todo:
            self.send_json_response(200, asdict(todo))
        else:
            self.send_error_response(404, f"Todo {todo_id} not found")

    def handle_delete(self, todo_id: int) -> None:
        if store.delete(todo_id):
            self.send_json_response(200, {"deleted": todo_id})
        else:
            self.send_error_response(404, f"Todo {todo_id} not found")
    # @pyweb:end id="1966fb8d"

    # @pyweb:start id="1e89c3a0" name="other stuff"
    def read_body(self) -> dict[str, Any] | None:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return None
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def send_json_response(self, code: int, data: Any) -> None:
        body = json.dumps(data, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_error_response(self, code: int, message: str) -> None:
        self.send_json_response(code, {"error": message})

    def log_message(self, format: str, *args: Any) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {args[0]}")
    # @pyweb:end id="1e89c3a0"
# @pyweb:end id="d89d3b92"

# @pyweb:start id="8071e4d1" name="main runner"
def run(host: str = "localhost", port: int = 8080) -> None:
    server = HTTPServer((host, port), RequestHandler)
    print(f"Todo API running at http://{host}:{port}")
    print("Endpoints:")
    print("  GET    /todos          - list all todos")
    print("  GET    /todos/:id      - get a todo")
    print("  GET    /todos/search?q= - search todos")
    print("  GET    /todos/stats    - get stats")
    print("  POST   /todos          - create a todo")
    print("  POST   /todos/:id/toggle - toggle done")
    print("  DELETE /todos/:id      - delete a todo")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    run()
# @pyweb:end id="8071e4d1"
# @pyweb:end id="0e6262b0"
