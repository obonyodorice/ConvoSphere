from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import UserActivity, UserConnection
from django.utils import timezone
import random

User = get_user_model()

class Command(BaseCommand):
    help = 'Populate database with demo data for testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--users',
            type=int,
            default=50,
            help='Number of demo users to create',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting demo data population...'))
        
        # Create demo users
        users_count = options['users']
        created_users = self.create_demo_users(users_count)
        
        # Create user activities
        self.create_user_activities(created_users)
        
        # Create user connections
        self.create_user_connections(created_users)
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {len(created_users)} demo users with activities!')
        )

    def create_demo_users(self, count):
        """Create demo users with varied profiles"""
        first_names = [
            'Alice', 'Bob', 'Charlie', 'Diana', 'Emma', 'Frank', 'Grace', 'Henry',
            'Isabel', 'Jack', 'Kate', 'Liam', 'Maya', 'Noah', 'Olivia', 'Paul',
            'Quinn', 'Rachel', 'Sam', 'Tara', 'Uma', 'Victor', 'Wendy', 'Xavier',
            'Yuki', 'Zoe', 'Alex', 'Blake', 'Casey', 'Drew'
        ]
        
        last_names = [
            'Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller',
            'Davis', 'Rodriguez', 'Martinez', 'Hernandez', 'Lopez', 'Gonzalez',
            'Wilson', 'Anderson', 'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin'
        ]
        
        roles = ['member', 'moderator', 'speaker', 'member', 'member']  # More members
        locations = [
            'New York, NY', 'San Francisco, CA', 'London, UK', 'Tokyo, Japan',
            'Berlin, Germany', 'Toronto, Canada', 'Sydney, Australia', 'Mumbai, India',
            'São Paulo, Brazil', 'Moscow, Russia', 'Seoul, South Korea', 'Paris, France'
        ]
        
        bio_templates = [
            "Passionate about technology and community building. Love connecting with like-minded people!",
            "Software developer by day, community enthusiast by night. Always learning something new.",
            "Digital nomad exploring the world while building amazing products. Let's connect!",
            "Experienced in project management and team collaboration. Here to share knowledge.",
            "Creative designer with a love for user experience. Excited to be part of this community!",
            "Entrepreneur and startup mentor. Happy to help others on their journey.",
            "Data scientist passionate about using data to solve real-world problems.",
            "Full-stack developer and open-source contributor. Always up for a good discussion!",
            "Product manager with experience in building user-centric solutions.",
            "Community manager who loves bringing people together and fostering connections."
        ]

        created_users = []
        
        for i in range(count):
            try:
                first_name = random.choice(first_names)
                last_name = random.choice(last_names)
                username = f"{first_name.lower()}{last_name.lower()}{i}"
                email = f"{username}@example.com"
                
                # Check if user already exists
                if User.objects.filter(email=email).exists():
                    continue
                
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password='demopassword123',
                    first_name=first_name,
                    last_name=last_name,
                    bio=random.choice(bio_templates),
                    location=random.choice(locations),
                    role=random.choice(roles),
                    is_online=random.choice([True, False, False]),  # Some users online
                    reputation_score=random.randint(0, 1000),
                    total_posts=random.randint(0, 50),
                    total_events_attended=random.randint(0, 10),
                )
                
                # Set some users as email verified
                if random.random() > 0.3:
                    user.email_verified = True
                    user.save()
                
                created_users.append(user)
                
                if (i + 1) % 10 == 0:
                    self.stdout.write(f'Created {i + 1} users...')
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error creating user {i}: {str(e)}')
                )
                continue
        
        return created_users

    def create_user_activities(self, users):
        """Create realistic user activities"""
        activity_types = ['login', 'logout', 'forum_post', 'profile_update', 'event_join']
        activity_descriptions = {
            'login': ['Logged into the platform', 'Started a new session'],
            'logout': ['Logged out', 'Session ended'],
            'forum_post': [
                'Posted in General Discussion',
                'Started a new topic about Django',
                'Replied to a question about Python',
                'Shared experience with React',
                'Asked for advice on career development'
            ],
            'profile_update': [
                'Updated profile picture',
                'Added new bio information',
                'Updated location',
                'Added website link'
            ],
            'event_join': [
                'Joined upcoming webinar',
                'Registered for community meetup',
                'Signed up for workshop',
                'Joined virtual conference'
            ]
        }
        
        for user in users:
            # Create 5-15 activities per user
            num_activities = random.randint(5, 15)
            
            for _ in range(num_activities):
                activity_type = random.choice(activity_types)
                description = random.choice(activity_descriptions[activity_type])
                
                # Create activity with random timestamp in the last 30 days
                days_ago = random.randint(0, 30)
                hours_ago = random.randint(0, 23)
                minutes_ago = random.randint(0, 59)
                
                timestamp = timezone.now() - timezone.timedelta(
                    days=days_ago, 
                    hours=hours_ago, 
                    minutes=minutes_ago
                )
                
                UserActivity.objects.create(
                    user=user,
                    activity_type=activity_type,
                    description=description,
                    timestamp=timestamp,
                    ip_address=f"192.168.1.{random.randint(1, 254)}"
                )

    def create_user_connections(self, users):
        """Create random follow relationships between users"""
        connections_created = 0
        
        for user in users:
            # Each user follows 3-8 other users
            num_to_follow = random.randint(3, 8)
            potential_follows = [u for u in users if u != user]
            follows = random.sample(potential_follows, min(num_to_follow, len(potential_follows)))
            
            for follow_user in follows:
                # Check if connection already exists
                if not UserConnection.objects.filter(
                    follower=user, 
                    following=follow_user
                ).exists():
                    UserConnection.objects.create(
                        follower=user,
                        following=follow_user
                    )
                    connections_created += 1
        
        self.stdout.write(f'Created {connections_created} user connections')

    def create_superuser_if_needed(self):
        """Create superuser for admin access"""
        if not User.objects.filter(is_superuser=True).exists():
            User.objects.create_superuser(
                username='admin',
                email='admin@example.com',
                password='admin123',
                first_name='Admin',
                last_name='User'
            )
            self.stdout.write('Created superuser: admin/admin123')