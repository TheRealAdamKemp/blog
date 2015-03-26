<!-- !b
kind: post
service: blogger
title: Decoupling Views In Multi-Screen Sequences
url: http://blog.adamkemp.com/2015/03/decoupling-views-advanced-ux-flows.html
labels: mobile, ios, android, xamarin, decoupling, software-engineering, xamarin-forms, cohesion, navigation
blog: 6425054342484936402
draft: False
id: 1644327527281380491
-->

In my [previous post](http://blog.adamkemp.com/2015/03/decoupling-views.html) I explained how to decouple individual views and why that is a good idea. In this post I will take that idea further and explain how to use this concept in more advanced UX scenarios involving multi-screen sequences.

<!--more-->

[TOC]

Motivation
==========

As a summary, the benefits of decoupling views are increased flexibility and allowing for more code reuse. For instance, a particular type of view may be used in multiple parts of your application in slightly different scenarios. If that view makes assumptions about where it fits within the whole app then it would be difficult to reuse that view in a different part of the app.

Still, at some level in your application you need to build in some kind of knowledge of which view is next. In the last post I gave a basic example where that knowledge lived in the `Application` class. There are many situations in which the `Application` class may be the best place for this kind of app-wide navigation logic, but some situations are more advanced and require a more sophisticated technique.

For example, it is also common to have a series of views within an app that always go together, but that sequence as a whole may be launched from different parts of the application. On iOS this kind of reusable sequence of views can be represented in a [Storyboard](http://developer.xamarin.com/guides/ios/user_interface/introduction_to_storyboards/)[^storyboard], but we can achieve the same result in code.

[^storyboard]: I do not actually recommend using iOS storyboards for multiple reasons, which I may eventually get around to documenting in a blog post.

An Example
==========

As an example let's consider a sequence of views for posting a picture to a social network:

1. Choose a picture from a library or choose to take a new picture.
2. If the user chose to take a new picture then show the camera view.
3. After the user has either chosen a picture or taken a new picture he can add a comment.
4. The picture is posted.

At any point during this process the user should also have the option to cancel, which should return the user back to where he started.

Here are some questions to consider when implementing this UX flow:

* How can we handle the cancel button in a way that avoids code duplication?
* How can we avoid code duplication for the various parts of the app that might want to invoke this sequence? For instance, perhaps you can post a picture either to your own profile or on someone else's profile or in a comment or in a private message.
* How can we allow for flexibility such that different parts of the app can do different things with the chosen picture/comment?

The first two questions are about code reuse, which is one of our goals. We want to avoid both having these individual screens duplicate code to accomplish the same thing, and we also want to avoid duplication of code from elsewhere in our app. The last question is about how we can decouple this code itself from the act of _using_ the results of the sequence (i.e., the picture and the comment). This is important because each part of the app that might use this probably has to do slightly different things with the results.

Creating the Views
==================

The example flow has three unique screens:

1. A screen that lets the user choose an image or choose to take a new picture.
2. A screen for taking a picture.
3. A screen for entering a comment.

As per my last post, each of these views should be written to be agnostic about how it's used. There may be yet another part of the application that allows for editing a comment on an existing post, and you probably want to reuse the same view (#3) for that use case. Therefore you shouldn't make any assumptions when implementing that view about how it will be used.

To accomplish this each view could be written with events for getting the results. Their APIs might look like this:

    :::csharp
    
    public class ImageEventArgs : EventArgs
    {
        public Image Image { get; private set; }

        public ImageEventArgs(Image image)
        {
            Image = image;
        }
    }

    public class CommentEventArgs : EventArgs
    {
        public string Comment { get; private set; }

        public CommentEventArgs(string comment)
        {
            Comment = comment;
        }
    }

    public class ImagePickerPage : ContentPage
    {
        public event EventHandler TakeNewImage;

        public event EventHandler<ImageEventArgs> ImageChosen;

        // ...
    }

    public class CameraPage : ContentPage
    {
        public event EventHandler<ImageEventArgs> PictureTaken;

        // ...
    }

    public class ImageCommentPage : ContentPage
    {
        public event EventHandler<CommentEventArgs> CommentEntered;

        public ImageCommentPage(Image image)
        {
            // ...
        }

        // ...
    }

Constructing the Sequence
=========================

Now that we have our building blocks we need to put it all together. To do that we will create a new class that represents the whole sequence. This new class doesn't need to be a view itself. Instead, it is just an object that manages the sequence. It will be responsible for creating each page as needed, putting them on the screen, and combining the results. Its public API might look like this:

    :::csharp
    public class CommentedImageSequenceResults
    {
        public static CommentedImageSequenceResults CanceledResult = new CommentedImageSequenceResults();

        public bool Canceled { get; private set; }

        public Image Image { get; private set; }

        public string Comment { get; private set; }

        public CommentedImageSequenceResults(Image image, string comment)
        {
            Image = image;
            Comment = comment;
        }

        private CommentedImageSequenceResults()
        {
            Canceled = true;
        }
    }

    public class CommentedImageSequence
    {
        public static Task<CommentedImageSequenceResults> ShowAsync(INavigation navigation)
        {
            // ...
        }

        // ...
    }

Notice that in this case I've chosen to simplify the API by using a `Task<T>` instead of multiple events. This plays nicely with C#'s `async`/`await` feature. I could have done the same with each of the individual views as well, but I wanted to show both approaches. Here is an example of how this API could be used:

    :::csharp
    public class ProfilePage : ContentPage
    {
        // ...

        private async void HandleAddImageButtonPressed(object sender, EventArgs e)
        {
            var results = await CommentedImageSequence.ShowAsync(Navigation);
            if (!results.Canceled)
            {
                PostImage(results.Image, results.Comment);
            }
        }
    }

Of course you could have similar code elsewhere in the app, but what you do with the results would be different. That satisfies our requirements of flexibility and avoiding code duplication.

Now let's look at how you would actually implement the sequence:


    :::csharp
    public class CommentedImageSequence
    {
        private readonly TaskCompletionSource<CommentedImageSequenceResults> _taskCompletionSource = new TaskCompletionSource<CommentedImageSequenceResults>();

        private readonly NavigationPage _navigationPage;
        private readonly ToolbarItem _cancelButton;

        private Image _image;

        private CommentedImageSequence()
        {
            _cancelButton = new ToolbarItem("Cancel", icon: null, activated: HandleCancel);
            _navigationPage = new NavigationPage(CreateImagePickerPage());
        }

        private void AddCancelButton(Page page)
        {
            page.ToolbarItems.Add(_cancelButton);
        }

        private ImagePickerPage CreateImagePickerPage()
        {
            var page = new ImagePickerPage();
            AddCancelButton(page);
            page.TakeNewImage += HandleTakeNewImage;
            page.ImageChosen += HandleImageChosen;
            return page;
        }

        private CameraPage CreateCameraPage()
        {
            var page = new CameraPage();
            AddCancelButton(page);
            page.PictureTaken += HandleImageChosen;
            return page;
        }

        private ImageCommentPage CreateImageCommentPage()
        {
            var page = new ImageCommentPage(_image);
            AddCancelButton(page);
            page.CommentEntered += HandleCommentEntered;
            return page;
        }

        private async void HandleTakeNewImage(object sender, EventArgs e)
        {
            await _navigationPage.PushAsync(CreateCameraPage());
        }

        private async void HandleImageChosen(object sender, ImageEventArgs e)
        {
            _image = e.Image;
            await _navigationPage.PushAsync(CreateImageCommentPage());
        }

        private void HandleCommentEntered(object sender, CommentEventArgs e)
        {
            _taskCompletionSource.SetResult(new CommentedImageSequenceResults(_image, e.Comment));
        }

        private void HandleCancel()
        {
            _taskCompletionSource.SetResult(CommentedImageSequenceResults.CanceledResult);
        }

        public static async Task<CommentedImageSequenceResults> ShowAsync(INavigation navigation)
        {
            var sequence = new CommentedImageSequence();
            
            await navigation.PushModalAsync(sequence._navigationPage);

            var results = await sequence._taskCompletionSource.Task;

            await navigation.PopModalAsync();

            return results;
        }
    }

Let's summarize what this class does:

1. It creates the `NavigationPage` used for displaying the series of pages and allowing the user to go back, and it presents that page (modally).
2. It creates the cancel button that allows the user to cancel. Notice how only one cancel button needed to be created, and it is handled in only one place. Code reuse!
3. It creates each page in the sequence as needed and pushes it onto the `NavigationPage`'s stack.
4. It keeps track of all of the information gathered so far. That is, once a user has taken or captured an image it holds onto that image while waiting for the user to enter a comment. Once the comment is entered it can return both the image and the comment together.
5. It dismisses everything when done.

Now we can easily show this whole sequence of views from anywhere in our app with just a single line of code. If we later decide to tweak the order of the views (maybe we decide to ask for the comment first for some reason) then we don't have to change any of those places in the app that invoke this sequence. We just have to change this one class. Likewise, if we decide that we don't want a modal view and instead we want to reuse an existing `NavigationPage` then we just touch this one class. That's because all of the navigation calls for this whole sequence (presenting the modal navigation page, pushing views, and popping the modal) are in a single, cohesive class.

Summary
=======

This technique can be used for any self-contained sequence of views within an application, including the app as a whole if you wanted. You can also compose these sequences if needed (that is, one sequence could reuse another sequence as part of its implementation). This is a powerful pattern for keeping code decoupled and [cohesive](http://en.wikipedia.org/wiki/Cohesion_(computer_science)). Anytime you find yourself wanting to put a call to `PushAsync` or `PushModalAsync` (or the equivalent on other platforms) within a view itself you should stop and think about how you could restructure that code to keep all of the navigation in one place.
