# FloodSense LK - Authentication Setup Summary

## ✅ Completed Setup

### Frontend Changes
1. **Profile Dropdown Component** (`src/components/layout/ProfileDropdown.tsx`)
   - Interactive user profile menu with logout button
   - Shows user name, email, and role
   - Styled with consistent theme (dark navy with blue accents)
   - Sign Out functionality using Clerk's `signOut()`

2. **Updated Topbar** (`src/components/layout/Topbar.tsx`)
   - Integrated ProfileDropdown
   - Shows actual user data from Zustand auth store
   - Dynamically loads user info on client side
   - Proper loading state handling

3. **Auth Store Integration** (`src/store/useAuthStore.ts`)
   - Already configured with user role support
   - ClerkSync component automatically syncs Clerk state

### Backend Database Changes
1. **Users Table Migration** (`migrations/sql/0003_users_table.sql`)
   - Creates PostgreSQL `users` table
   - Fields: clerk_id, email, full_name, role, is_active, timestamps
   - Proper indexes and constraints

2. **Alembic Migration Version** (`migrations/versions/0003_users_table.py`)
   - Python migration file following existing pattern

3. **Admin Setup Script** (`scripts/setup-admin-user.py`)
   - Command-line tool to create/update admin users
   - Syncs to database with admin role

### Documentation
- **Admin Setup Guide** (`docs/admin-setup.md`)
  - Step-by-step instructions
  - Troubleshooting guide
  - Testing procedures

---

## 🔐 Available Login Types

### 1. **Regular User (Citizen)**
- **Sign Up**: http://localhost:3000/sign-up
- **Sign In**: http://localhost:3000/sign-in
- **Role**: citizen (default)
- **Access**: View-only features, personal profile
- **Setup**: Create account via Sign Up page

### 2. **Admin User**
- **Sign In**: http://localhost:3000/sign-in
- **Role**: admin
- **Access**: All features, admin dashboard, user management
- **Setup**: 
  1. Create user in Clerk Dashboard
  2. Run: `python scripts/setup-admin-user.py <clerk_id> <email> <name>`
  3. Set public_metadata role in Clerk to "admin"

### 3. **Field Officer**
- **Sign In**: http://localhost:3000/sign-in
- **Role**: field_officer
- **Access**: Field operations, sensor management
- **Setup**: Set role in Clerk public_metadata to "field_officer"

---

## 🚀 Quick Start: Create Admin User

1. **In Clerk Dashboard**:
   - Create user with email: `admin@flodsense.lk`
   - Note the User ID: `user_2abc123xyz` (example)

2. **In Terminal**:
   ```bash
   cd flood-backend
   alembic upgrade head  # Apply migrations
   python scripts/setup-admin-user.py user_2abc123xyz admin@flodsense.lk "Admin User"
   ```

3. **In Clerk Dashboard** (again):
   - Click the admin user
   - Go to Public metadata
   - Set: `{"role": "admin"}`
   - Save

4. **Test**:
   - Go to http://localhost:3000/sign-in
   - Sign in with admin@flodsense.lk
   - Verify profile dropdown shows admin role

---

## 📋 Authentication Flow

```
User Action → Clerk Auth → JWT Token → Frontend Store → UI Display
                              ↓
                        Backend Validation
                              ↓
                      Role-Based Access Control
```

### Sign In Flow
1. User visits http://localhost:3000/sign-in
2. Enters credentials in Clerk form
3. Clerk validates and generates JWT
4. Frontend middleware redirects to dashboard
5. ClerkSync component updates Zustand store
6. Topbar displays user info and role
7. Profile dropdown available on click

### Sign Out Flow
1. User clicks profile dropdown (top-right)
2. Clicks "Sign Out" button
3. Clerk signs out and clears JWT
4. Frontend redirects to sign-in page
5. Auth store is cleared

### Role-Based Features
- **Admin**: All API endpoints (`/api/rbac/admin-test`)
- **Field Officer**: Operations endpoints (`/api/rbac/field-test`)
- **Citizen**: Basic endpoints (`/api/rbac/citizen-test`)

---

## 📝 Database Schema

### users table
```sql
clerk_id      VARCHAR(255) PRIMARY KEY  -- Unique ID from Clerk
email         VARCHAR(255) NOT NULL UNIQUE
full_name     VARCHAR(255)
role          VARCHAR(50) DEFAULT 'citizen'  -- admin, field_officer, citizen
is_active     BOOLEAN DEFAULT TRUE
created_at    TIMESTAMPTZ DEFAULT NOW()
updated_at    TIMESTAMPTZ DEFAULT NOW()
```

---

## 🔗 Webhook Integration

The Clerk webhook endpoint is configured at:
- **URL**: `POST /v1/webhooks/clerk`
- **Events**: user.created, user.updated, user.deleted
- **Auto-sync**: Users are automatically synced to database

### Configure in Clerk Dashboard:
1. Go to **Webhooks**
2. Add endpoint: `https://your-backend/api/v1/webhooks/clerk`
3. Select events: user.created, user.updated, user.deleted
4. Use CLERK_WEBHOOK_SECRET for verification

---

## 🛠️ Tech Stack Summary

### Frontend Authentication
- **Provider**: Clerk + Next.js
- **State Management**: Zustand
- **Components**: ProfileDropdown, RoleGate, ClerkSync
- **Styling**: CSS Modules (Dark theme, blue accents)

### Backend Authentication
- **Provider**: Clerk JWT
- **Validation**: RS256 signature verification
- **Database**: PostgreSQL
- **Sync**: Webhook-based

### Supported Roles
- `admin` - Full system access
- `field_officer` - Field operations
- `citizen` - End users

---

## ✨ Key Features

✅ Sign In with Clerk OAuth/SSO
✅ Sign Up for new users
✅ Profile dropdown with logout
✅ Role-based access control
✅ Automatic user sync via webhooks
✅ Admin user management
✅ Consistent theme styling (dark navy + blue)
✅ Mobile-responsive design
✅ Real-time auth state

---

## 📱 Testing UI Components

### Profile Dropdown
- **Location**: Top-right corner of dashboard
- **Trigger**: Click avatar or user name
- **Shows**: Name, email, role badge
- **Options**: 
  - View Profile (disabled - for future)
  - Settings (disabled - for future)
  - Sign Out (working)

### Sign In Page
- **URL**: http://localhost:3000/sign-in
- **Features**: Email/password, OAuth options
- **Redirect**: To dashboard on success
- **Theme**: Dark background matching app theme

### Sign Up Page
- **URL**: http://localhost:3000/sign-up
- **Features**: Email, password, name fields
- **Redirect**: To dashboard on success
- **Theme**: Dark background matching app theme

---

## 🐛 Troubleshooting

### Profile dropdown not showing real user data
- Solution: Ensure ClerkSync component is in app layout
- Check: `src/app/layout.tsx` has ClerkSync wrapper

### Logout button not working
- Solution: Verify Clerk is properly initialized
- Check: `.env` has CLERK_PUBLISHABLE_KEY and CLERK_SECRET_KEY

### Role not appearing in profile
- Solution: Set public_metadata in Clerk Dashboard
- Check: Format is exactly `{"role": "admin"}`

### Admin script fails with database error
- Solution: Run migration first: `alembic upgrade head`
- Check: Database connection string is correct

---

## 📚 Files Modified/Created

### Frontend
- ✨ `src/components/layout/ProfileDropdown.tsx` (new)
- ✨ `src/components/layout/ProfileDropdown.module.css` (new)
- 📝 `src/components/layout/Topbar.tsx` (updated)

### Backend
- ✨ `migrations/sql/0003_users_table.sql` (new)
- ✨ `migrations/versions/0003_users_table.py` (new)
- ✨ `scripts/setup-admin-user.py` (new)
- 📝 `docs/admin-setup.md` (new)

---

## 🎯 Next Steps

1. **Run Database Migration**
   ```bash
   cd flood-backend
   alembic upgrade head
   ```

2. **Create Admin User**
   ```bash
   # Get user ID from Clerk Dashboard first
   python scripts/setup-admin-user.py user_YOUR_ID your@email.com "Your Name"
   ```

3. **Test Sign In**
   - Visit http://localhost:3000/sign-in
   - Sign in with your credentials
   - Verify profile dropdown appears

4. **Test Sign Out**
   - Click profile dropdown
   - Click "Sign Out"
   - Verify redirect to sign-in page

5. **Test Role-Based Features**
   - As admin, test admin endpoints
   - Verify role badge in profile

---

## 📞 Support

For more details, see:
- `docs/admin-setup.md` - Complete admin setup guide
- `app/auth/clerk.py` - Backend auth logic
- `app/api/routers/webhooks.py` - Webhook handler
- `src/components/auth/ClerkSync.tsx` - Frontend sync logic
