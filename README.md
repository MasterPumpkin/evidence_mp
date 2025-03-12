# Evidence MP - System for Managing Thesis Projects

## Overview
Evidence MP is a comprehensive Django application designed for managing, tracking, and evaluating student thesis projects. The system facilitates collaboration between students, project supervisors, and opponents through a well-structured workflow.

## Features

### Project Management
- Project creation and management for students and teachers
- Multiple project statuses (pending approval, approved, etc.)
- Rich text description and documentation support
- Official project assignment handling
- Support for both internal and external project leaders and opponents

### Milestone Tracking
- Create, update, and monitor project milestones
- Track milestone status (not started, in progress, completed)
- Visual indicators for milestone deadlines and status
- CSV import functionality for bulk milestone creation

### Evaluation System
- Structured evaluation forms for both supervisors and opponents
- Multi-criteria assessment system based on configurable scoring schemes
- Question management for project defense
- Document generation for reviews and evaluations
- Final assessment report generation

### Documentation
- Support for project documentation uploads 
- Portfolio URL management (GitHub, personal websites, etc.)
- Internal notes system for teachers

### Control Checks
- Scheduled control checks for project progress
- Evaluation and feedback recording
- Automatic control check generation based on templates

### Exports
- DOCX export for supervisor evaluation
- DOCX export for opponent evaluation
- PDF export for project details
- DOCX export for project assignment
- PDF export for final reports
- Export functionality for consultation lists

### User Management
- Student profiles
- Teacher profiles
- User preferences and settings
- Support for signatures in generated documents

## Technical Details

### Technologies Used
- Django 5.1.4
- PostgreSQL database
- CKEditor 5 for rich text editing
- Bootstrap 5 for frontend UI
- Crispy Forms for form rendering
- WeasyPrint for PDF generation
- DocxTemplate for DOCX generation

### Project Structure
- `apps/projects` - Core application for project management
- `apps/profiles` - User profile management
- `templates` - HTML templates for the application
- `media` - User-uploaded files (signatures, etc.)
- `static` - Static files (CSS, JS, images)

### Key Models
- `Project` - Main project entity with details and metadata
- `Milestone` - Project milestone tracking
- `ControlCheck` - Scheduled control checks and evaluations
- `LeaderEvaluation` - Supervisor's evaluation data
- `OpponentEvaluation` - Opponent's evaluation data
- `ScoringScheme` - Configurable scoring criteria and deadlines
- `UserPreferences` - User-specific settings and preferences

## Installation

1. Clone the repository
2. Set up a virtual environment
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Configure your environment variables in a `.env` file:
   ```
   DEBUG=True
   SECRET_KEY=your-secret-key
   DB_NAME=your-db-name
   DB_USER=your-db-user
   DB_PASSWORD=your-db-password
   DB_HOST=localhost
   ```
5. Run migrations:
   ```
   python manage.py migrate
   ```
6. Create a superuser:
   ```
   python manage.py createsuperuser
   ```
7. Start the development server:
   ```
   python manage.py runserver
   ```

## Usage
Access the admin interface at `/admin/` and the main application at the root URL. Log in with your credentials to start using the system.

## License
This project is provided for educational purposes only. All rights reserved.