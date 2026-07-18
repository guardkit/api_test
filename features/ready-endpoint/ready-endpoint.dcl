language dcl 1.0
// @task:TASK-READY-001

actor HealthChecker is system

shape ReadinessRequest {
  method: Text
}

capability CheckReadiness {
  intent ReadinessRequest from HealthChecker
  outcomes {
    Ready
    MethodNotAllowed
  }
  rules {
    AllowedGet: method is GET
  }
  when {
    AllowedGet violated then MethodNotAllowed
    otherwise then Ready
  }
}