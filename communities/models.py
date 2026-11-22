
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.templatetags.static import static


# 1. COMMUNITY MODEL
class Community(models.Model):

    COMMUNITY_TYPES = [('college', 'College'), ('hostel', 'Hostel'), ('neighbourhood', 'Neighbourhood'), ('other', 'Other')]

    name = models.CharField(max_length=100)
    community_type = models.CharField(max_length=20, choices=COMMUNITY_TYPES)
    location = models.CharField(max_length=200)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Communities"

    @property
    def cover_url(self):
        return static('home/img/type-%s.svg' % self.community_type)

    def __str__(self):
        return self.name


# 2. MEMBERSHIP MODEL
class Membership(models.Model):

    STATUS_CHOICES = [('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    community = models.ForeignKey(Community, on_delete=models.CASCADE)
    ROLE_CHOICES = [('member', 'Member'), ('moderator', 'Moderator')]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'community')

    def __str__(self):
        return self.user.username + " - " + self.community.name


# Keyword -> cartoon picture used when a listing has no photo of its own
PRODUCT_ART = [('backpack', 'backpack'), ('calculator', 'calculator'), ('laptop', 'laptop'), ('bicycle', 'bicycle'), ('cycle', 'bicycle'),
               ('book', 'books'), ('headphone', 'headphones'), ('earphone', 'headphones'), ('lamp', 'lamp'),
               ('chair', 'chair'), ('jacket', 'jacket'), ('hoodie', 'jacket'), ('phone', 'phone'),
               ('wallet', 'wallet'), ('key', 'keys'), ('kettle', 'kettle'), ('cooker', 'kettle'),
               ('bag', 'backpack'), ('guitar', 'guitar')]


# 3. MARKETPLACE LISTING MODEL
class Listing(models.Model):

    CATEGORIES = [('books', 'Books'), ('electronics', 'Electronics'), ('clothing', 'Clothing'), ('furniture', 'Furniture'), ('other', 'Other')]
    STATUS_CHOICES = [('available', 'Available'), ('sold', 'Sold'), ('lent', 'Lent out')]
    LISTING_TYPES = [('sell', 'Sell'), ('lend', 'Lend')]
    
    listing_type = models.CharField(max_length=10, choices=LISTING_TYPES, default='sell')
    seller = models.ForeignKey(User, on_delete=models.CASCADE)
    community = models.ForeignKey(Community, on_delete=models.CASCADE)
    title = models.CharField(max_length=150)
    description = models.TextField()
    category = models.CharField(max_length=30, choices=CATEGORIES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image_url = models.URLField(blank=True)
    image = models.ImageField(upload_to='listings/', blank=True)
    RENT_UNITS = [('hour', 'per hour'), ('day', 'per day'), ('week', 'per week'), ('month', 'per month')]
    rent_unit = models.CharField(max_length=10, choices=RENT_UNITS, default='day')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def price_label(self):
        """'₹120' for sale items, '₹20 / day' for lending items (price = rent per unit)."""
        price = Decimal(str(self.price))
        amount = price.quantize(Decimal('1')) if price == price.to_integral() else price
        if self.listing_type == 'lend':
            return '₹%s / %s' % (amount, self.rent_unit)
        return '₹%s' % amount

    @property
    def picture_url(self):
        """Uploaded photo, else pasted URL, else a category illustration."""
        if self.image:
            return self.image.url
        if self.image_url:
            return self.image_url
        text = (self.title + ' ' + self.description).lower()
        for word, file in PRODUCT_ART:
            if word in text:
                return static('home/img/p-%s.svg' % file)
        return static('home/img/cat-%s.svg' % self.category)

    def __str__(self):
        return self.title


# 4. BORROW REQUEST MODEL
class BorrowRequest(models.Model):

    STATUS_CHOICES = [('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('returned', 'Returned')]

    listing = models.ForeignKey(Listing, on_delete=models.CASCADE)
    borrower = models.ForeignKey(User, on_delete=models.CASCADE)
    return_date = models.DateField()
    units = models.PositiveIntegerField(default=1)  # how many hours/days/weeks/months
    message = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    requested_at = models.DateTimeField(auto_now_add=True)

    @property
    def total_rent(self):
        return self.listing.price * self.units

    def __str__(self):
        return self.borrower.username + " - " + self.listing.title


# 5. LOST AND FOUND MODEL
class LostFoundItem(models.Model):

    ITEM_TYPES = [('lost', 'Lost'), ('found', 'Found')]
    STATUS_CHOICES = [('open', 'Open'), ('resolved', 'Resolved')]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    community = models.ForeignKey(Community, on_delete=models.CASCADE)
    item_type = models.CharField(max_length=10, choices=ITEM_TYPES)
    title = models.CharField(max_length=150)
    description = models.TextField()
    location = models.CharField(max_length=200)
    contact = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.item_type + " - " + self.title


# 6. NOTICEBOARD MODEL
class Notice(models.Model):

    NOTICE_TYPES = [('announcement', 'Announcement'), ('event', 'Event'), ('general', 'General Notice'),
                    ('issue', 'Issue / Complaint'), ('help', 'Help wanted')]
    MEMBER_TYPES = ['issue', 'help', 'general']  # types any approved member may post

    community = models.ForeignKey(Community, on_delete=models.CASCADE)
    title = models.CharField(max_length=150)
    content = models.TextField()
    notice_type = models.CharField(max_length=20, choices=NOTICE_TYPES)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    is_pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


# 7. NOTIFICATION MODEL
class Notification(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.CharField(max_length=255)
    link = models.CharField(max_length=200, blank=True, default='')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username + " - " + self.message[:40]


# 8. COMMUNITY REQUEST MODEL (a student asks admin to add a new community)
class CommunityRequest(models.Model):

    STATUS_CHOICES = [('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    community_type = models.CharField(max_length=20, choices=Community.COMMUNITY_TYPES)
    location = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name + " (requested by " + self.user.username + ")"


# 9. REPORT MODEL (a member reports a listing or a lost/found post)
class Report(models.Model):

    STATUS_CHOICES = [('open', 'Open'), ('resolved', 'Resolved')]

    reporter = models.ForeignKey(User, on_delete=models.CASCADE)
    community = models.ForeignKey(Community, on_delete=models.CASCADE)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, null=True, blank=True)
    lost_item = models.ForeignKey(LostFoundItem, on_delete=models.CASCADE, null=True, blank=True)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def target_title(self):
        return (self.listing or self.lost_item).title

    def __str__(self):
        return "Report by " + self.reporter.username


# 10. PROFILE (phone + UPI id, used for payments and sharing WhatsApp)
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15, blank=True)
    upi_id = models.CharField(max_length=60, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True)  # profile picture shown in the navbar menu

    @property
    def avatar_url(self):
        return self.avatar.url if self.avatar else ''

    def __str__(self):
        return "Profile of " + self.user.username


# 11. ORDER (buying an item that is listed for sale)
class Order(models.Model):

    METHODS = [('upi', 'UPI'), ('cash', 'Cash on meeting')]
    STATUS_CHOICES = [('awaiting', 'Awaiting payment'), ('paid', 'Payment sent'), ('confirmed', 'Confirmed'),
                      ('cancelled', 'Cancelled')]

    listing = models.ForeignKey(Listing, on_delete=models.CASCADE)
    buyer = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=10, choices=METHODS, default='upi')
    note = models.TextField(blank=True)
    upi_ref = models.CharField(max_length=40, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='awaiting')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return "Order #%s %s" % (self.pk, self.listing.title)


# 12. CHAT (a conversation between two members, optionally about a listing)
class Conversation(models.Model):

    STATUS_CHOICES = [('pending', 'Pending'), ('accepted', 'Accepted'), ('declined', 'Declined')]

    starter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chats_started')
    other = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chats_received')
    listing = models.ForeignKey(Listing, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    starter_shared = models.BooleanField(default=False)  # starter chose to share WhatsApp
    other_shared = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def partner(self, user):
        return self.other if user == self.starter else self.starter

    def __str__(self):
        return "%s <-> %s" % (self.starter.username, self.other.username)


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    body = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
